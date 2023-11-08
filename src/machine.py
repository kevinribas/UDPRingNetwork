import sys
import time
import socket
import random
import logging
import datetime
import threading
from .packet import Packet
from .data_packet import DataPacket
from .token_packet import TokenPacket
from .file_handler import FlushingFileHandler

class Machine:
    def __init__(self, ip: str, nickname: str, time_token: str, has_token: bool = False, 
                 error_probability: float = 0.2, TIMEOUT_VALUE: int = 100, MINIMUM_TIME: int = 2, 
                 local_ip: str = "127.0.0.1", local_port: int = 6000) -> None:
        """
        Args:
            ip (str): "ip:porta" da próxima máquina da rede
            nickname (str): Nome da máquina
            time_token (str): Tempo que a máquina segura o token
            has_token (bool, optional): Se a máquina está com o token.
            error_probability (float, optional): Probabilidade de erro na transmissão. 
            TIMEOUT_VALUE (int, optional): Tempo máximo permitido sem ver o token. 
            MINIMUM_TIME (int, optional): Tempo mínimo esperado entre as passagens do token.
            local_ip (str, optional): IP da máquina local. 
            local_port (int, optional): Porta da máquina local. Por padrão, 6000.
        """        
        # Initialize machine properties
        self.ip, self.port = self._extract_ip_and_port(ip)
        self.local_ip = local_ip
        self.local_port = local_port
        self.nickname = nickname
        self.time_token = time_token
        self.error_probability = error_probability
        self.TIMEOUT_VALUE = TIMEOUT_VALUE 
        self.MINIMUM_TIME = MINIMUM_TIME
        self.has_token = has_token
        self.last_token_time = None if not has_token else datetime.datetime.now()
        self.controls_token = self.has_token
        self.message_queue = []
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((local_ip, local_port))
        if self.has_token:
            self.generate_token()
        self.logger = logging.getLogger('MachineLogger')
        self.logger.setLevel(logging.DEBUG)
        fh = FlushingFileHandler(f"logs/{self.nickname}_log.log", "a")
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
    def start(self):
        self.terminate_event = threading.Event()
        if self.controls_token:
            self.token_checker_thread = threading.Thread(target=self.check_token_status)
            self.token_checker_thread.start()
        self.listen_thread = threading.Thread(target=self.listen_for_packets)
        self.listen_thread.start()
        self.user_interaction_thread = threading.Thread(target=self.user_interaction)
        self.user_interaction_thread.start()
        self.logger.debug('-'*50)
        self.logger.debug(f"Host {self.nickname} started.")
        self.logger.debug('-'*50+'\n\n')
        if self.has_token:
            self.logger.debug('-'*50)
            self.logger.debug(f"Host {self.nickname} has the token. Sleeping for {self.time_token} seconds")
            self.logger.debug('-'*50+'\n\n')
            time.sleep(int(self.time_token))
            self.send_packet(self.token)
            self.has_token = False
            self.last_token_time = datetime.datetime.now()

    @staticmethod
    def _extract_ip_and_port(ip: str) -> tuple:    
        # Separates IP address and port from an string
        ip_address, port = ip.split(":")
        return ip_address, int(port)

    def generate_token(self):
        # Generate a token
        self.token = TokenPacket()
        self.has_token = True
        self.last_token_time = datetime.datetime.now()

    def add_packet_to_queue(self, packet: Packet):   
        # Add a packet to the message queue
        self.message_queue.append(packet)

    def send_packet(self, packet: Packet, add_error_chance: bool = False):
        # Send a packet through the socket, with optional error introduction
        self.logger.debug('-'*50)
        if isinstance(packet, DataPacket):
            self.logger.debug("Sending data packet...")
        elif isinstance(packet, TokenPacket):
            self.logger.debug("Sending token...")
        if isinstance(packet, DataPacket) and random.random() < self.error_probability:
            if add_error_chance == True:
                bit_to_invert = random.randint(0, 31)
                mask = 1 << bit_to_invert
                packet.crc ^= mask
                packet.header = packet.create_header()
                self.logger.debug(f"Error introduced on packet with the following destination: {packet.destination_name}")   
        self.socket.sendto(packet.header.encode(), (self.ip, self.port)) 
        if isinstance(packet, DataPacket):
            self.logger.debug("Data packet sent.")
            self.logger.debug('-'*50+'\n\n')
        elif isinstance(packet, TokenPacket):
            self.logger.debug("Token sent.")
            self.logger.debug('-'*50+'\n\n')
        
    def receive_packet(self): 
        # Receive and process a packet
        data, _ = self.socket.recvfrom(1024) # recebe o pacote
        packet_type = Packet.get_packet_type(data.decode()) # pega o tipo do pacote
        packet = TokenPacket() if packet_type == "1000" else DataPacket.create_header_from_string(data.decode()) # cria o pacote a partir do header recebido
        if isinstance(packet, DataPacket):
            packet.crc = int(data.decode().split(":")[3]) # pega o crc do pacote
        self.logger.debug('-'*50)
        self.logger.debug("Packet received. Processing...")
        return self.process_packet(packet)
            
    @classmethod
    # Create a machine instance from a configuration file
    def create_machine_from_file(cls, file_path: str, local_ip: str = "127.0.0.1", local_port: int = 6000,
                                 TIMEOUT_VALUE: int = 100, MINIMUM_TIME: int = 2, error_probability: float = 0.2): 
        with open(file_path, 'r') as file:
            ip_and_port, nickname, time_token, has_token_str = [file.readline().strip() for _ in range(4)]
            has_token = has_token_str.lower() == "true"
        return cls(ip_and_port, nickname, time_token, has_token, local_ip=local_ip, local_port=local_port, 
                   TIMEOUT_VALUE=TIMEOUT_VALUE, MINIMUM_TIME=MINIMUM_TIME, error_probability=error_probability)
    
    def close_socket(self):      
        # Close the machine's socket
        self.socket.close()   
        
    def run(self):     
        if self.has_token == True:
            if len(self.message_queue) > 0: 
                self.logger.debug(f"Holding token for {self.time_token} seconds...")
                time.sleep(int(self.time_token))  
                self.logger.debug("Sending message...")
                packet = self.message_queue[0]
                self.send_packet(packet, add_error_chance=True)
            else:
                self.logger.debug(f"No messages to be sent, holding token for {self.time_token} seconds...")
                self.logger.debug('-'*50+'\n\n')
                time.sleep(int(self.time_token))  
                self.send_packet(self.token)
                self.has_token = False
                self.last_token_time = datetime.datetime.now()
        else:
            pass
        
    def process_packet(self, packet: Packet):
        if packet.id == "1000":
            self.last_token_time = datetime.datetime.now()
            self.logger.debug("Token received.")
            if not self.has_token:
                self.has_token = True
                self.token = packet
                self.run()
            else:
                self.send_packet(self.token)
            
        elif packet.id == "2000":
            if packet.destination_name == self.nickname:
                self.logger.debug(f"Packet :) Received from: {packet.origin_name}")
                calculated_crc = packet.calculate_crc() # crc
                if calculated_crc == packet.crc:
                    packet.error_control = "ACK"
                    self.logger.debug(f"Message received: {packet.message}")
                else:
                    packet.error_control = "NACK"
                    self.logger.debug(f"Message has errors. Wrong CRC!")
                self.logger.debug("Sending packet back...")
                self.logger.debug('-'*50+'\n')
                packet.header = packet.create_header()
                self.send_packet(packet) 
            elif packet.origin_name == self.nickname:
                self.logger.debug(f"Packet received back! From ME -> {packet.destination_name}")
                self.logger.debug(f"Message: {packet.message}")
                if packet.error_control == "ACK":
                    self.logger.debug(f"Message sent was received by the destination")
                    self.message_queue.pop(0)
                    self.logger.debug("Packet removed from the queue")
                    self.logger.debug("Sending token...")
                    self.send_packet(self.token)
                    self.has_token = False
                    self.last_token_time = datetime.datetime.now()    
                elif packet.error_control == "NACK":
                    self.logger.debug("Message has errors, NACK error control.")
                    self.logger.debug("Keeping the message in the queue and sending the token...")
                    self.message_queue[0].crc = self.message_queue[0].calculate_crc()
                    self.message_queue[0].header = self.message_queue[0].create_header()
                    self.send_packet(self.token)
                    self.has_token = False
                    self.last_token_time = datetime.datetime.now()
                elif packet.error_control == "maquinanaoexiste":
                    self.logger.debug("Host not found. Removing the packet from the queue...")
                    self.message_queue.pop(0)
                    self.logger.debug("Sending token...")
                    self.send_packet(self.token)
                    self.has_token = False
                    self.last_token_time = datetime.datetime.now()
            elif packet.destination_name == "BROADCAST":
                self.logger.debug("BROADCAST!")
                if packet.origin_name == self.nickname:
                    self.logger.debug("Packet received back! From ME -> ALL")
                    self.logger.debug(f"Message: {packet.message}")
                    self.logger.debug("Packet removed from the queue")
                    self.logger.debug("Passing token...")
                    self.message_queue.pop(0)
                    self.send_packet(self.token)
                    self.has_token = False
                    self.last_token_time = datetime.datetime.now()
                else:
                    calculated_crc = packet.calculate_crc()
                    if calculated_crc == packet.crc:
                        self.logger.debug(f"Message received: {packet.message}")
                        packet.error_control = "ACK"
                    else:
                        self.logger.debug(f"Message has errors. Wrong CRC!")
                        packet.error_control = "NACK"
                self.logger.debug("Sending packet back...")
                self.logger.debug('-'*50+'\n\n')
                packet.header = packet.create_header()
                self.send_packet(packet)
            else:
                self.logger.debug(f"Packet is not for me. Sent by {packet.origin_name} to {packet.destination_name}. Passing...\n")
                self.send_packet(packet)
   
    def check_token_status(self):      
        time_waiting = 0
        while not self.terminate_event.is_set():
            if self.has_token == False:
                while time_waiting < self.TIMEOUT_VALUE and self.has_token == False:
                    time_waiting = (datetime.datetime.now() - self.last_token_time).total_seconds()
                    time.sleep(0.1)
                if time_waiting >= self.TIMEOUT_VALUE:
                    self.logger.debug('\n'+'-'*56+'\n'+f"| No token. Generating a new token. |"+'\n'+'-'*56+'\n')
                    self.generate_token()
                    self.send_packet(self.token)
                    self.token = None
                    self.has_token = False
                    self.last_token_time = datetime.datetime.now()
                    time_waiting = 0
                    self.logger.debug("A new token has been added. Sending it forward.")
                elif time_waiting < self.MINIMUM_TIME:
                    self.logger.debug('\n'+'-'*60+'\n'+f"| Too fast. Removing the token. |"+'\n'+'-'*60+'\n')
                    self.has_token = False
                    self.token = None
                    self.logger.debug("The token has been removed.")

    def listen_for_packets(self):
        while not self.terminate_event.is_set():
            try:
                self.receive_packet()
            except Exception as e:
                continue
            
    def stop_listening(self):
        try:
            self.listen_thread.join(timeout=5)
        except Exception as e:
            self.logger.debug(f"Error joining listen_thread: {e}")
        if self.controls_token:
            try:
                self.token_checker_thread.join(timeout=5)
            except Exception as e:
                self.logger.debug(f"Error joining token_checker_thread: {e}")
        self.close_socket()

    def user_interaction(self):     
        while not self.terminate_event.is_set():
            print("\nOptions:")
            print("1. Add a new packet to the queue")
            print("2. Turn off")
            print("3. Message queue")
            print("4. Remove the token")
            choice = input("Enter your choice: ")
            if choice == "1":
                print("Token (1000) or Data (2000).")
                packet_type = input("Packet type: ")
                if packet_type == "2000":
                    destination_name = input("Destination name: ")
                    message = input("Enter a message: ")
                    new_packet = DataPacket(origin_name=self.nickname, destination_name=destination_name, error_control="maquinanaoexiste", message=message)
                    print(f"Packet added to the queue. Sending it to {destination_name}. Message: {message}")
                    self.add_packet_to_queue(new_packet)
                elif packet_type == "1000":
                    token = TokenPacket()
                    self.send_packet(token)
                    self.last_token_time = datetime.datetime.now()
                    print(f"A new token has been created")
                    self.logger.debug(f"A new token has been created")
                else:
                    print("Invalid type. Try again.")
            elif choice == "2":
                print("Turning off...")
                self.terminate_event.set()
                self.stop_listening()
                print("Exited.")
                sys.exit(0)
            elif choice == "3":
                print("Message queue:")
                for packet in self.message_queue:
                    print(packet.message)     
            elif choice == "4":
                if self.has_token:
                    print("Removing the token from the network...")
                    self.has_token = False
                    self.token = None
                    print("The token has been removed.")
                else:
                    while self.has_token == False:
                        pass
                    self.has_token = False
                    self.token = None
                    print("The token has been removed.")
            else:
                print("Invalid choice. Try again.")

import zlib
from .packet import Packet

class DataPacket(Packet):

    def __init__(self, origin_name: str, destination_name: str, error_control: str, message: str = "") -> None:
        super().__init__("2000")
        self.origin_name = origin_name
        self.destination_name = destination_name 
        self.error_control = error_control
        self.message = message
        self.crc = self.calculate_crc()
        self.header = self.create_header()
        
    def create_header(self):   
        return f"{self.id};{self.origin_name}:{self.destination_name}:{self.error_control}:{self.crc}:{self.message}"
    
    def calculate_crc(self) -> int:    
        return zlib.crc32(self.message.encode())
    
    
    @classmethod
    def create_header_from_string(cls, header: str):      
        header = header.split(";")
        content = header[1].split(':')
        return DataPacket(content[0], content[1], content[2], content[4])

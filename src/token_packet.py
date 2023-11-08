from .packet import Packet

class TokenPacket(Packet):

    def __init__(self) -> None:
        super().__init__("1000")
        self.header = self.create_header()
        
        
    def create_header(self):   
        return f"{self.id}"
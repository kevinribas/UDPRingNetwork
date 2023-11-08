from abc import ABC, abstractmethod

class Packet(ABC):

    def __init__(self, id: str) -> None:
        self.id = id
        
    @abstractmethod
    def create_header(self):     
        pass
    
    @classmethod
    def get_packet_type(cls, header: str):  
        return header.split(";")[0]
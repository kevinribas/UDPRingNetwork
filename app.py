from src.machine import Machine

machine = Machine.create_machine_from_file("config/machine.txt", 
                                       local_port=6000, 
                                       local_ip="127.0.0.1",
                                       TIMEOUT_VALUE=12, 
                                       MINIMUM_TIME=1, 
                                       error_probability=0.5)
machine.start()

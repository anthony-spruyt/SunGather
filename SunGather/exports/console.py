class export_console(object):
    def __init__(self):
        pass

    # Configure Console
    def configure(self, _config, inverter):
        print("+----------------------------------------------+")
        print(f"{'| Inverter Configuration Settings':<46} {'|':<1}")
        print("+----------------------------------------------+")
        print(f"{'| Config':<20} {'| Value':<25} {'|':<1}")
        print("+--------------------+-------------------------+")
        for setting, value in inverter.client_config.items():
            print(f"{'| ' + str(setting):<20} {'| ' + str(value):<25} {'|':<1}")
        for setting, value in inverter.inverter_config.items():
            print(f"{'| ' + str(setting):<20} {'| ' + str(value):<25} {'|':<1}")
        print("+----------------------------------------------+")

        return True

    def publish(self, inverter):
        print("+----------------------------------------------------------------------+")
        print(f"| {'Address':<7} | {'Register':<35} | {'Value':<20} |")
        print("+---------+-------------------------------------+----------------------+")
        for register, value in inverter.latest_scrape.items():
            print(f"| {str(inverter.getRegisterAddress(register)):<7} | {str(register):<35}"
                  f" | {str(value) + ' ' + str(inverter.getRegisterUnit(register)):<20} |")
        print("+----------------------------------------------------------------------+")
        print(f"Logged {len(inverter.latest_scrape)} registers to Console")

        return True

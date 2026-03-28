#!/usr/bin/python3

import logging
import logging.handlers
import time
from datetime import datetime

from pymodbus.client import ModbusTcpClient

from version import __version__
from .sungrow_modbus_tcp_client import SungrowModbusTcpClient
from .sungrow_modbus_web_client import SungrowModbusWebClient

class SungrowClient():
    def __init__(self, config_inverter):

        logging.info('Loading SungrowClient %s', __version__)

        self.client_config = {
            "host":     config_inverter.get('host'),
            "port":     config_inverter.get('port'),
            "timeout":  config_inverter.get('timeout'),
            "retries":  config_inverter.get('retries'),
        }
        self.inverter_config = {
            "model":            config_inverter.get('model'),
            "serial_number":    config_inverter.get('serial_number'),
            "level":            config_inverter.get('level'),
            "scan_interval":    config_inverter.get('scan_interval'),
            "use_local_time":   config_inverter.get('use_local_time'),
            "smart_meter":      config_inverter.get('smart_meter'),
            "connection":       config_inverter.get('connection'),
            "slave":            config_inverter.get('slave'),
            "start_time":       ""
        }
        self.client = None

        self.registers = [[]]
        self.registers.pop() # Remove null value from list
        self.registers_custom = [
            {'name': 'run_state', 'address': 'vr001'},
            {'name': 'timestamp', 'address': 'vr002'},
            {'name': 'last_reset', 'address': 'vr003'},
            {'name': 'export_to_grid', 'unit': 'W', 'address': 'vr004'},
            {'name': 'import_from_grid', 'unit': 'W', 'address': 'vr005'},
            {'name': 'daily_export_to_grid', 'unit': 'kWh', 'address': 'vr006'},
            {'name': 'daily_import_from_grid', 'unit': 'kWh', 'address': 'vr007'},
        ]

        self.register_ranges = [[]]
        self.register_ranges.pop() # Remove null value from list

        self.latest_scrape = {}

    def connect(self):
        if self.client:
            try: self.client.connect()
            except: return False
            return True

        host = self.client_config['host']
        config = {k: v for k, v in self.client_config.items() if k != 'host'}

        if self.inverter_config['connection'] == "http":
            config['port'] = 8082
            # host passed as keyword — SungrowModbusWebClient declares it with a default,
            # unlike the other clients
            self.client = SungrowModbusWebClient(host=host, **config)
        elif self.inverter_config['connection'] == "sungrow":
            self.client = SungrowModbusTcpClient(host, **config)
        elif self.inverter_config['connection'] == "modbus":
            self.client = ModbusTcpClient(host, **config)
        else:
            logging.warning(
                "Inverter: Unknown connection type %s, Valid options are http, sungrow or modbus",
                self.inverter_config['connection']
            )
            return False
        logging.info("Connection: %s", self.client)

        try: self.client.connect()
        except: return False

        time.sleep(3)
        return True

    def checkConnection(self):
        logging.debug("Checking Modbus Connection")
        if self.client:
            if self.client.connected:
                logging.debug("Modbus, Session is still connected")
                return True
            else:
                logging.info('Modbus, Connecting new session')
                return self.connect()
        else:
            logging.info('Modbus client is not connected, attempting to reconnect')
            return self.connect()

    def close(self):
        logging.info("Closing Session: %s", self.client)
        try: self.client.close()
        except: pass

    def disconnect(self):
        logging.info("Disconnecting: %s", self.client)
        try: self.client.close()
        except: pass
        self.client = None

    def configure_registers(self,registersfile):
        # Check model so we can load only valid registers
        if self.inverter_config.get('model'):
            logging.info(
                "Bypassing Model Detection, Using config: %s", self.inverter_config.get('model')
            )
        else:
            # Load just the register to detect model, then load the rest based on returned model
            for register in registersfile['registers'][0]['read']:
                if register.get('name') == "device_type_code":
                    register['type'] = "read"
                    self.registers.append(register)
                    if self.load_registers(register['type'], register['address'] - 1, 1):
                        if isinstance(self.latest_scrape.get('device_type_code'), int):
                            logging.warning(
                                "Unknown Type Code Detected: %s",
                                self.latest_scrape.get('device_type_code')
                            )
                        else:
                            self.inverter_config['model'] = (
                                self.latest_scrape.get('device_type_code')
                            )
                            logging.info(
                                "Detected Model: %s", self.inverter_config.get('model')
                            )
                    else:
                        logging.info('Model detection failed, please set model in config.py')
                    self.registers.pop()
                    break

        if self.inverter_config.get('serial_number'):
            logging.info(
                "Bypassing Serial Detection, Using config: %s",
                self.inverter_config.get('serial_number')
            )
        else:
            # Load just the register to detect serial number, then load the rest based on model
            for register in registersfile['registers'][0]['read']:
                if register.get('name') == "serial_number":
                    register['type'] = "read"
                    self.registers.append(register)
                    if self.load_registers(register['type'], register['address'] - 1, 10):
                        if isinstance(self.latest_scrape.get('serial_number'), int):
                            logging.warning(
                                "Unknown Type Code Detected: %s",
                                self.latest_scrape.get('serial_number')
                            )
                        else:
                            self.inverter_config['serial_number'] = (
                                self.latest_scrape.get('serial_number')
                            )
                            logging.info(
                                "Detected Serial: %s", self.inverter_config.get('serial_number')
                            )
                    else:
                        logging.info(
                            'Serial detection failed, please set serial number in config.py'
                        )
                    self.registers.pop()
                    break

        # Load register list based on name and value after checking model
        for register in registersfile['registers'][0]['read']:
            if (register.get('level', 3) <= self.inverter_config.get('level')
                    or self.inverter_config.get('level') == 3):
                register['type'] = "read"
                register.pop('level')
                if register.get('smart_meter') and self.inverter_config.get('smart_meter'):
                    register.pop('models')
                    self.registers.append(register)
                elif register.get('models') and not self.inverter_config.get('level') == 3:
                    for supported_model in register.get('models'):
                        if supported_model == self.inverter_config.get('model'):
                            register.pop('models')
                            self.registers.append(register)
                else:
                    self.registers.append(register)

        for register in registersfile['registers'][1]['hold']:
            if (register.get('level', 3) <= self.inverter_config.get('level')
                    or self.inverter_config.get('level') == 3):
                register['type'] = "hold"
                register.pop('level')
                if register.get('smart_meter') and self.inverter_config.get('smart_meter'):
                    register.pop('models')
                    self.registers.append(register)
                elif register.get('models') and not self.inverter_config.get('level',1) == 3:
                    for supported_model in register.get('models'):
                        if supported_model == self.inverter_config.get('model'):
                            register.pop('models')
                            self.registers.append(register)
                else:
                    self.registers.append(register)

        # Load register list based om name and value after checking model
        for register_range in registersfile['scan'][0]['read']:
            register_range_used = False
            register_range['type'] = "read"
            for register in self.registers:
                if register.get("type") == register_range.get("type"):
                    if (register.get('address') >= register_range.get("start")
                        and register.get('address') <= (
                            register_range.get("start") + register_range.get("range")
                        )):
                        register_range_used = True
                        continue
            if register_range_used:
                self.register_ranges.append(register_range)


        for register_range in registersfile['scan'][1]['hold']:
            register_range_used = False
            register_range['type'] = "hold"
            for register in self.registers:
                if register.get("type") == register_range.get("type"):
                    if (register.get('address') >= register_range.get("start")
                        and register.get('address') <= (
                            register_range.get("start") + register_range.get("range")
                        )):
                        register_range_used = True
                        continue
            if register_range_used:
                self.register_ranges.append(register_range)
        return True

    def load_registers(self, register_type, start, count=100):
        try:
            logging.debug('load_registers: %s, %s:%s', register_type, start, count)
            if register_type == "read":
                rr = self.client.read_input_registers(
                    start, count=count, device_id=self.inverter_config['slave']
                )
            elif register_type == "hold":
                rr = self.client.read_holding_registers(
                    start, count=count, device_id=self.inverter_config['slave']
                )
            else:
                raise RuntimeError(f"Unsupported register type: {type}")
        except Exception as err:
            logging.warning("No data returned for %s, %s:%s", register_type, start, count)
            logging.debug("%s", err)
            return False

        if rr.isError():
            logging.warning("Modbus connection failed")
            logging.debug("%s", rr)
            return False

        if not hasattr(rr, 'registers'):
            logging.warning("No registers returned")
            return False

        if len(rr.registers) != count:
            logging.warning(
                "Mismatched number of registers read %s != %s", len(rr.registers), count
            )
            return False

        for num in range(0, count):
            run = int(start) + num + 1

            for register in self.registers:
                if register_type == register['type'] and register['address'] == run:
                    register_name = register['name']

                    register_value = rr.registers[num]

                    # Convert unsigned to signed
                    # If xFF / xFFFF then change to 0, looks better when logging / graphing
                    if register.get('datatype') == "U16":
                        if register_value == 0xFFFF:
                            register_value = 0
                        if register.get('mask'):
                            # Filter the value through the mask.
                            register_value = 1 if register_value & register.get('mask') != 0 else 0
                    elif register.get('datatype') == "S16":
                        if register_value == 0xFFFF or register_value == 0x7FFF:
                            register_value = 0
                        if register_value >= 32767:  # Anything > 32767 is negative for 16bit
                            register_value = (register_value - 65536)
                    elif register.get('datatype') == "U32":
                        u32_value = rr.registers[num+1]
                        if register_value == 0xFFFF and u32_value == 0xFFFF:
                            register_value = 0
                        else:
                            register_value = (register_value + u32_value * 0x10000)
                    elif register.get('datatype') == "S32":
                        u32_value = rr.registers[num+1]
                        s32_zero = (u32_value == 0xFFFF or u32_value == 0x7FFF)
                        if register_value == 0xFFFF and s32_zero:
                            register_value = 0
                        elif u32_value >= 32767:  # Anything greater than 32767 is a negative
                            register_value = (register_value + u32_value * 0x10000 - 0xffffffff -1)
                        else:
                            register_value = register_value + u32_value * 0x10000
                    elif register.get('datatype') == "UTF-8":  # Serial only, 10 bytes
                        utf_value = register_value.to_bytes(2, 'big')
                        for x in range(1,5):
                            utf_value += rr.registers[num+x].to_bytes(2, 'big')
                        register_value = utf_value.decode()


                    # We convert a system response to a human value
                    if register.get('datarange'):
                        match = False
                        for value in register.get('datarange'):
                            if value['response'] == rr.registers[num]:
                                register_value = value['value']
                                match = True
                        if not match:
                            default = register.get('default')
                            logging.debug(
                                "No matching value for %s in datarange of %s, using default %s",
                                register_value, register_name, default
                            )
                            register_value = default

                    if register.get('accuracy'):
                        register_value = round(register_value * register.get('accuracy'), 2)

                    # Set the final register value with adjustments above included
                    self.latest_scrape[register_name] = register_value
        return True

    def validateRegister(self, check_register):
        for register in self.registers:
            if check_register == register['name']:
                return True
        for register in self.registers_custom:
            if check_register == register['name']:
                return True
        return False

    def getRegisterAddress(self, check_register):
        for register in self.registers:
            if check_register == register['name']:
                return register['address']
        for register in self.registers_custom:
            if check_register == register['name']:
                return register['address']
        return '----'

    def getRegisterUnit(self, check_register):
        for register in self.registers:
            if check_register == register['name']:
                return register.get('unit','')
        for register in self.registers_custom:
            if check_register == register['name']:
                return register.get('unit','')
        return ''

    def validateLatestScrape(self, check_register):
        for register, value in self.latest_scrape.items():
            if check_register == register:
                return True
        return False

    def getRegisterValue(self, check_register):
        for register, value in self.latest_scrape.items():
            if check_register == register:
                return value
        return False

    def getHost(self):
        return self.client_config['host']

    def getInverterModel(self, clean=False):
        if clean:
            return self.inverter_config['model'].replace('.','').replace('-','')
        else:
            return self.inverter_config['model']

    def getSerialNumber(self):
        return self.inverter_config['serial_number']

    def scrape(self):
        scrape_start = datetime.now()

        # Clear previous inverter values, persist some values
        persist_registers = {
            "run_state":                self.latest_scrape.get("run_state","ON"),
            "last_reset":               self.latest_scrape.get("last_reset",""),
            "daily_export_to_grid":     self.latest_scrape.get("daily_export_to_grid",0),
            "daily_import_from_grid":   self.latest_scrape.get("daily_import_from_grid",0),
        }

        self.latest_scrape = {}
        self.latest_scrape['device_type_code'] = self.inverter_config['model']

        for register, value in persist_registers.items():
            self.latest_scrape[register] = value

        load_registers_count = 0
        load_registers_failed = 0

        for range in self.register_ranges:
            load_registers_count +=1
            logging.debug(
                'Scraping: %s, %s:%s', range.get("type"), range.get("start"), range.get("range")
            )
            rng_type = range.get('type')
            rng_start = int(range.get('start'))
            rng_range = int(range.get('range'))
            if not self.load_registers(rng_type, rng_start, rng_range):
                load_registers_failed +=1
        if load_registers_failed == load_registers_count:
            # If every scrape fails, disconnect the client
            #logging.warning
            self.disconnect()
            return False
        if load_registers_failed > 0:
            logging.info(
                'Scraping: %s/%s registers failed to scrape',
                load_registers_failed, load_registers_count
            )

        # Leave connection open, see if helps resolve the connection issues
        #self.close()

        ## vr002
        if self.inverter_config.get('use_local_time',False):
            self.latest_scrape["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.debug('Using Local Computer Time: %s', self.latest_scrape.get("timestamp"))
            del self.latest_scrape["year"]
            del self.latest_scrape["month"]
            del self.latest_scrape["day"]
            del self.latest_scrape["hour"]
            del self.latest_scrape["minute"]
            del self.latest_scrape["second"]
        else:
            try:
                self.latest_scrape["timestamp"] = "%s-%s-%s %s:%02d:%02d" % (
                    self.latest_scrape["year"],
                    self.latest_scrape["month"],
                    self.latest_scrape["day"],
                    self.latest_scrape["hour"],
                    self.latest_scrape["minute"],
                    self.latest_scrape["second"],
                )
                logging.debug('Using Inverter Time: %s', self.latest_scrape.get("timestamp"))
                del self.latest_scrape["year"]
                del self.latest_scrape["month"]
                del self.latest_scrape["day"]
                del self.latest_scrape["hour"]
                del self.latest_scrape["minute"]
                del self.latest_scrape["second"]
            except Exception:
                self.latest_scrape["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logging.warning(
                    'Failed to get Timestamp from Inverter, using Local Time: %s',
                    self.latest_scrape.get("timestamp")
                )
                del self.latest_scrape["year"]
                del self.latest_scrape["month"]
                del self.latest_scrape["day"]
                del self.latest_scrape["hour"]
                del self.latest_scrape["minute"]
                del self.latest_scrape["second"]
                pass

        # If alarm state exists then convert to timestamp, otherwise remove it
        try:
            if self.latest_scrape["pid_alarm_code"]:
                self.latest_scrape["alarm_timestamp"] = "%s-%s-%s %s:%02d:%02d" % (
                    self.latest_scrape["alarm_time_year"],
                    self.latest_scrape["alarm_time_month"],
                    self.latest_scrape["alarm_time_day"],
                    self.latest_scrape["alarm_time_hour"],
                    self.latest_scrape["alarm_time_minute"],
                    self.latest_scrape["alarm_time_second"],
                )
            del self.latest_scrape["alarm_time_year"]
            del self.latest_scrape["alarm_time_month"]
            del self.latest_scrape["alarm_time_day"]
            del self.latest_scrape["alarm_time_hour"]
            del self.latest_scrape["alarm_time_minute"]
            del self.latest_scrape["alarm_time_second"]
        except Exception:
            pass

        ### Custom Registers
        ######################

        ## vr001 - run_state
        # See if the inverter is running, This is added to inverters so can be read via MQTT etc...
        # It is also used below, as some registers hold the last value on 'stop' so we set to 0
        # to help with graphing.
        try:
            if self.latest_scrape.get('start_stop'):
                logging.debug(
                    "start_stop:%s work_state_1:%s",
                    self.latest_scrape.get('start_stop', 'null'),
                    self.latest_scrape.get('work_state_1', 'null')
                )
                if (self.latest_scrape.get('start_stop', False) == 'Start'
                        and self.latest_scrape.get('work_state_1', False).contains('Run')):
                    self.latest_scrape["run_state"] = "ON"
                else:
                    self.latest_scrape["run_state"] = "OFF"
            else:
                logging.info("DEBUG: Couldn't read start_stop so run_state is OFF")
                self.latest_scrape["run_state"] = "OFF"
        except Exception:
            pass

        ## vr003 - last_reset
        date_format = "%Y-%m-%d %H:%M:%S"
        if not self.latest_scrape.get('last_reset', False):
            logging.info(
                'Setting Initial Daily registers; '
                'daily_export_to_grid, daily_import_from_grid, last_reset'
            )
            self.latest_scrape["daily_export_to_grid"] = 0
            self.latest_scrape["daily_import_from_grid"] = 0
            self.latest_scrape['last_reset'] = self.latest_scrape["timestamp"]
        elif (datetime.strptime(self.latest_scrape['last_reset'], date_format).date()
              < datetime.strptime(self.latest_scrape['timestamp'], date_format).date()):
            logging.info(
                'last_reset: %s, timestamp: %s',
                self.latest_scrape['last_reset'], self.latest_scrape['timestamp']
            )
            logging.info(
                'Resetting Daily registers; '
                'daily_export_to_grid, daily_import_from_grid, last_reset'
            )
            self.latest_scrape["daily_export_to_grid"] = 0
            self.latest_scrape["daily_import_from_grid"] = 0
            self.latest_scrape['last_reset'] = self.latest_scrape["timestamp"]

        ## vr004 - import_from_grid, vr005 - export_to_grid
        # Create a registers for Power imported and exported to/from Grid
        if self.inverter_config['level'] >= 1:
            self.latest_scrape["export_to_grid"] = 0
            self.latest_scrape["import_from_grid"] = 0

            if self.validateRegister('meter_power'):
                try:
                    power = self.latest_scrape.get(
                        'meter_power', self.latest_scrape.get('export_power', 0)
                    )
                    if power < 0:
                        self.latest_scrape["export_to_grid"] = abs(power)
                    elif power >= 0:
                        self.latest_scrape["import_from_grid"] = power
                except Exception:
                    pass
            # in this case we connected to a hybrid inverter and need to use export_power_hybrid
            # export_power_hybrid is negative in case of importing from the grid
            elif self.validateRegister('export_power_hybrid'):
                try:
                    power = self.latest_scrape.get('export_power_hybrid', 0)
                    if power < 0:
                        self.latest_scrape["import_from_grid"] = abs(power)
                    elif power >= 0:
                        self.latest_scrape["export_to_grid"] = power
                except Exception:
                    pass

        try: # If inverter is returning no data for load_power, we can calculate it manually
            if not self.latest_scrape["load_power"]:
                self.latest_scrape["load_power"] = (
                    int(self.latest_scrape.get('total_active_power'))
                    + int(self.latest_scrape.get('meter_power'))
                )
        except Exception:
            pass

        ## vr004
        if not self.latest_scrape.get('daily_export_to_grid', False):
            self.latest_scrape["daily_export_to_grid"] = 0

        self.latest_scrape["daily_export_to_grid"] += (
            (self.latest_scrape["export_to_grid"] / 1000)
            * (self.inverter_config['scan_interval'] / 60 / 60)
        )

        ## vr005
        if not self.latest_scrape.get('daily_import_from_grid', False):
            self.latest_scrape["daily_import_from_grid"] = 0

        self.latest_scrape["daily_import_from_grid"] += (
            (self.latest_scrape["import_from_grid"] / 1000)
            * (self.inverter_config['scan_interval'] / 60 / 60)
        )

        scrape_end = datetime.now()
        elapsed = scrape_end - scrape_start
        logging.info(
            'Inverter: Successfully scraped in %s.%s secs',
            elapsed.seconds, elapsed.microseconds
        )

        return True

#!/usr/bin/python3

import getopt
import importlib
import logging
import logging.handlers
import signal
import sys
import time

import yaml

from client.sungrow_client import SungrowClient
from version import __version__

def main():
    configfilename = 'config.yaml'
    registersfilename = 'registers-sungrow.yaml'
    logfolder = ''
    runonce = False
    loglevel = None

    try:
        opts, args = getopt.getopt(sys.argv[1:],"hc:r:l:v:", "runonce")
    except getopt.GetoptError:
        sys.exit(f'No options passed via command line, use -h to see all options')


    for opt, arg in opts:
        if opt == '-h':
            print(f'\nSunGather {__version__}')
            print(f'\nhttps://sungather.app')
            print(f'usage: python3 sungather.py [options]')
            print(f'\nCommandling arguments override any config file settings')
            print(f'Options and arguments:')
            print(f'-c config.yaml             : Specify config file.')
            print(f'-r registers-file.yaml     : Specify registers file.')
            print(f'-l /logs/                  : Specify folder to store logs.')
            print(f'-v 30                      : Logging Level, 10 = Debug, 20 = Info, '
                  f'30 = Warning (default), 40 = Error')
            print(f'--runonce                  : Run once then exit')
            print(f'-h                         : print this help message and exit (also --help)')
            print(f'\nExample:')
            print(f'python3 sungather.py -c /full/path/config.yaml\n')
            sys.exit()
        elif opt == '-c':
            configfilename = arg
        elif opt == '-r':
            registersfilename = arg
        elif opt == '-l':
            logfolder = arg
        elif opt  == '-v':
            if arg.isnumeric():
                if int(arg) >= 0 and int(arg) <= 50:
                    loglevel = int(arg)
                else:
                    logging.error(
                        "Valid verbose options: 10=Debug, 20=Info, 30=Warning (default), 40=Error"
                    )
                    sys.exit(2)
            else:
                logging.error(
                    "Valid verbose options: 10=Debug, 20=Info, 30=Warning (default), 40=Error"
                )
                sys.exit(2)
        elif opt == '--runonce':
            runonce = True

    logging.info('Starting SunGather %s', __version__)
    logging.info('Need Help? https://github.com/anthony-spruyt/SunGather')

    try:
        configfile = yaml.safe_load(open(configfilename, encoding="utf-8"))
        logging.info("Loaded config: %s", configfilename)
    except Exception as err:
        logging.error("Failed: Loading config: %s \n\t\t\t     %s", configfilename, err)
        sys.exit(1)
    if not configfile.get('inverter'):
        logging.error("Failed Loading config, missing Inverter settings")
        sys.exit(f"Failed Loading config, missing Inverter settings")

    try:
        registersfile = yaml.safe_load(open(registersfilename, encoding="utf-8"))
        logging.info("Loaded registers: %s", registersfilename)
        logging.info("Registers file version: %s", registersfile.get('version','UNKNOWN'))
    except Exception as err:
        logging.error("Failed: Loading registers: %s  %s", registersfilename, err)
        sys.exit(f"Failed: Loading registers: {registersfilename} {err}")

    config_inverter = {
        "host": configfile['inverter'].get('host',None),
        "port": configfile['inverter'].get('port',502),
        "timeout": configfile['inverter'].get('timeout',10),
        "retries": configfile['inverter'].get('retries',3),
        "slave": configfile['inverter'].get('slave',0x01),
        "scan_interval": configfile['inverter'].get('scan_interval',30),
        "connection": configfile['inverter'].get('connection',"modbus"),
        "model": configfile['inverter'].get('model',None),
        "smart_meter": configfile['inverter'].get('smart_meter',False),
        "use_local_time": configfile['inverter'].get('use_local_time',False),
        "log_console": configfile['inverter'].get('log_console','WARNING'),
        "log_file": configfile['inverter'].get('log_file','OFF'),
        "level": configfile['inverter'].get('level',1)
    }

    if loglevel is not None:
        logger.handlers[0].setLevel(loglevel)
    else:
        logger.handlers[0].setLevel(config_inverter['log_console'])

    if not config_inverter['log_file'] == "OFF":
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if config_inverter['log_file'] in valid_log_levels:
            logfile = logfolder + "SunGather.log"
            fh = logging.handlers.RotatingFileHandler(  # Log 10mb files, 10 x files = 100mb
                logfile, mode='w', encoding='utf-8', maxBytes=10485760, backupCount=10
            )
            fh.formatter = logger.handlers[0].formatter
            fh.setLevel(config_inverter['log_file'])
            logger.addHandler(fh)
        else:
            logging.warning("log_file: Valid options are: DEBUG, INFO, WARNING, ERROR and OFF")

    logging.info("Logging to console set to: %s", logging.getLevelName(logger.handlers[0].level))
    if logger.handlers.__len__() == 3:
        logging.info("Logging to file set to: %s", logging.getLevelName(logger.handlers[2].level))

    logging.debug('Inverter Config Loaded: %s', config_inverter)

    if config_inverter.get('host'):
        inverter = SungrowClient(config_inverter)
    else:
        logging.error("Error: host option in config is required")
        sys.exit("Error: host option in config is required")

    if not inverter.checkConnection():
        logging.error(
            "Error: Connection to inverter failed: %s:%s",
            config_inverter.get('host'), config_inverter.get('port')
        )
        sys.exit(
            f"Error: Connection to inverter failed: "
            f"{config_inverter.get('host')}:{config_inverter.get('port')}"
        )

    inverter.configure_registers(registersfile)
    if not inverter.inverter_config['connection'] == "http": inverter.close()

    # Now we know the inverter is working, lets load the exports
    exports = []
    if configfile.get('exports'):
        for export in configfile.get('exports'):
            try:
                if export.get('enabled', False):
                    export_load = importlib.import_module("exports." + export.get('name'))
                    logging.info("Loading Export: exports %s", export.get('name'))
                    exports.append(getattr(export_load, "export_" + export.get('name'))())
                    retval = exports[-1].configure(export, inverter)
            except Exception as err:
                logging.error(
                    "Failed loading export: %s -- check %s.py exists in exports/",
                    err, export.get('name')
                )

    scan_interval = config_inverter.get('scan_interval')

    signal.signal(signal.SIGTERM, handle_sigterm)

    # Core polling loop
    while True:
        loop_start = time.perf_counter()

        inverter.checkConnection()

        # Scrape the inverter
        try:
            success = inverter.scrape()
        except Exception as e:
            logging.exception("Failed to scrape: %s", e)
            success = False

        if(success):
            for export in exports:
                export.publish(inverter)
            if not inverter.inverter_config['connection'] == "http": inverter.close()
        else:
            inverter.disconnect()
            logging.warning(
                "Data collection failed, skipped exporting data. Retying in %s secs",
                scan_interval
            )

        loop_end = time.perf_counter()
        process_time = round(loop_end - loop_start, 2)
        logging.debug('Processing Time: %s secs', process_time)

        if runonce:
            sys.exit(0)

        # Sleep until the next scan
        if scan_interval - process_time <= 1:
            logging.warning(
                "SunGather is taking %s to process, which is longer than interval %s, "
                "Please increase scan interval",
                process_time, scan_interval
            )
            time.sleep(process_time)
        else:
            logging.info('Next scrape in %s secs', int(scan_interval - process_time))
            time.sleep(scan_interval - process_time)

def handle_sigterm(signum, frame):
    print("Received SIGTERM, shutting down gracefully...")
    # Perform any cleanup here
    exit(0)

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.DEBUG,
    datefmt='%Y-%m-%d %H:%M:%S')

logger = logging.getLogger('')
ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)
logger.addHandler(ch)

if __name__== "__main__":
    main()

sys.exit()

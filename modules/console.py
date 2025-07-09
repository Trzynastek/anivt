import datetime, colorama, logging, os
from colorama import Fore, Back, Style

class instance:
    def __init__(self, debugMode=False, saveLogs=True):
        self.logger = logging.getLogger('anivt')
        self.logger.setLevel(logging.DEBUG if debugMode else logging.INFO)
        self.logger.handlers = []
        self.logger.propagate = False
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG if debugMode else logging.INFO)
        ch.addFilter(self.consoleFilter())
        self.logger.addHandler(ch)
        self.debugMode = debugMode
        if saveLogs:
            self.makeFile()
        self.saveLogs = saveLogs
        colorama.init()

    def consoleFilter(self):
        def filter(record):
            return getattr(record, 'target', 'console') == 'console'
        return filter
    
    def fileFilter(self):
        def filter(record):
            return getattr(record, 'target', 'console') == 'file'
        return filter

    def makeFile(self):
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        today = datetime.datetime.now().strftime('%d-%m-%Y')
        self.logDate = today
        file = f'logs/{today}.log'
        fh = logging.FileHandler(file)
        fh.setLevel(logging.DEBUG if self.debugMode else logging.INFO)
        fh.addFilter(self.fileFilter())
        self.logger.addHandler(fh)

    def updateFile(self):
        today = datetime.datetime.now().strftime('%d-%m-%Y')
        if today != self.logDate:
            self.logger.handlers = [h for h in self.logger.handlers if not isinstance(h, logging.FileHandler)]
            self.makeFile()


    def log(self, level, message, variables=None):
        if level == "DEBUG" and not self.debugMode:
            return
        
        if self.saveLogs:
            self.updateFile()
        
        time = f"{datetime.datetime.now().strftime('%H:%M:%S')}"

        var = ""
        if self.debugMode:
            if variables:
                var = f"\n{Fore.LIGHTBLACK_EX}" + "  ".join(f"{k}: {v};" for k, v in variables.items()) + f"{Style.RESET_ALL}"

        if level == "INFO":
            self.logger.info(f"{Back.LIGHTBLACK_EX}{Fore.BLACK} {time} {Style.RESET_ALL}{Back.GREEN}{Style.BRIGHT}{Fore.WHITE} {level} {Style.RESET_ALL} {message}{var}", extra={'target': 'console'})
            self.logger.info(f"{time} {level} {message}", extra={'target': 'file'})
        elif level == "WARN":
            self.logger.warning(f"{Back.LIGHTBLACK_EX}{Fore.BLACK} {time} {Style.RESET_ALL}{Back.YELLOW}{Style.BRIGHT}{Fore.WHITE} {level} {Style.RESET_ALL} {message}{var}", extra={'target': 'console'})
            self.logger.warning(f"{time} {level} {message}", extra={'target': 'file'})
        elif level == "ERROR":
            self.logger.error(f"{Back.LIGHTBLACK_EX}{Fore.BLACK} {time} {Style.RESET_ALL}{Back.RED}{Style.BRIGHT}{Fore.WHITE} {level} {Style.RESET_ALL} {message}{var}", extra={'target': 'console'})
            errorVar = f"\n" + " ".join(f"{k}: {v};" for k, v in variables.items())
            self.logger.error(f"{time} {level} {message} {errorVar}", extra={'target': 'file'})
        elif level == "DEBUG":
            self.logger.debug(f"{Back.LIGHTBLACK_EX}{Fore.BLACK} {time} {Style.RESET_ALL}{Back.BLUE}{Style.BRIGHT}{Fore.WHITE} {level} {Style.RESET_ALL} {message}{var}", extra={'target': 'console'})
            self.logger.debug(f"{time} {level} {message}", extra={'target': 'file'})

    def info(self, message, variables=None):
        self.log("INFO", message, variables)

    def warn(self, message, variables=None):
        self.log("WARN", message, variables)

    def error(self, message, variables=None):
        self.log("ERROR", message, variables)
    
    def debug(self, message, variables=None):
        self.log("DEBUG", message, variables)

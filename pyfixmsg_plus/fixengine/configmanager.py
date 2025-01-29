import configparser

#Ensure there's only one instance of ConfigManager (Singleton).
class ConfigManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConfigManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, config_path='config.ini'):
        if not hasattr(self, 'initialized'):
            self.config = configparser.ConfigParser()
            self.config_path = config_path
            self.load_config()
            self.initialized = True

    def load_config(self):
        self.config.read(self.config_path)

    def save_config(self):
        with open(self.config_path, 'w') as configfile:
            self.config.write(configfile)

    def get(self, section, option, fallback=None):
        return self.config.get(section, option, fallback=fallback)

    def set(self, section, option, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, value)

    def delete(self, section, option=None):
        if option:
            self.config.remove_option(section, option)
        else:
            self.config.remove_section(section)

    def reset(self):
        self.config = configparser.ConfigParser()
        self.save_config()

# Example usage
if __name__ == "__main__":
    cm1 = ConfigManager()
    cm2 = ConfigManager()
    cm1.load_config()
    print(cm1.get('FIX', 'sender_comp_id', 'SENDER'))
    cm1.set('FIX', 'new_option', 'new_value')
    cm1.save_config()
    cm2.delete('FIX', 'new_option')
    cm2.save_config()
    cm1.reset()
    cm1.save_config()

    # Check if both instances are the same
    print(cm1 is cm2)  # Should print: True

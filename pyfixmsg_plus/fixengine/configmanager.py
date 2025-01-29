import configparser

class ConfigManager:
    def __init__(self, config_path='config.ini'):
        self.config = configparser.ConfigParser()
        self.config_path = config_path

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
    cm = ConfigManager()
    cm.load_config()
    print(cm.get('FIX', 'sender_comp_id', 'SENDER'))
    cm.set('FIX', 'new_option', 'new_value')
    cm.save_config()
    cm.delete('FIX', 'new_option')
    cm.save_config()
    cm.reset()
    cm.save_config()

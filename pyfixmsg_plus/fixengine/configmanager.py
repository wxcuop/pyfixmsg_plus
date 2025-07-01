import configparser

# Ensure there's only one instance of ConfigManager (Singleton).
class ConfigManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path='config.ini'):
        if not hasattr(self, 'initialized'):
            self.config = configparser.ConfigParser()
            self.config_path = config_path
            self.load_config()
            self.initialized = True

    def load_config(self):
        try:
            self.config.read(self.config_path)
        except FileNotFoundError:
            print(f"Warning: Configuration file '{self.config_path}' not found. Using default settings.")

    def save_config(self):
        try:
            with open(self.config_path, 'w') as configfile:
                self.config.write(configfile)
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def get(self, section, option, fallback=None):
        try:
            return self.config.get(section, option, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError):
            print(f"Warning: Section '{section}' or option '{option}' not found. Returning fallback value.")
            return fallback

    def get_message_store_type(self, fallback='database'):
        """Gets the message store type from the config, e.g., 'database' or 'aiosqlite'."""
        return self.get('FIX', 'message_store_type', fallback=fallback)

    def set(self, section, option, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, value)

    def delete(self, section, option=None):
        if option:
            if self.config.has_section(section) and self.config.has_option(section, option):
                self.config.remove_option(section, option)
            else:
                print(f"Warning: Section '{section}' or option '{option}' not found.")
        else:
            if self.config.has_section(section):
                self.config.remove_section(section)
            else:
                print(f"Warning: Section '{section}' not found.")

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

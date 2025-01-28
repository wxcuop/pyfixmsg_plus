import os
import json

class SequenceManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self.sequence_number = self.load_sequence_number()

    def load_sequence_number(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as file:
                data = json.load(file)
                return data.get('sequence_number', 0)
        return 0

    def save_sequence_number(self, number):
        with open(self.filepath, 'w') as file:
            json.dump({'sequence_number': number}, file)

    def get_next_sequence_number(self):
        self.sequence_number += 1
        self.save_sequence_number(self.sequence_number)
        return self.sequence_number

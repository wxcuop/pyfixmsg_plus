def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.iteritems())
    enums['reverse_mapping'] = reverse
    return type('Enum', (), enums)
#http://stackoverflow.com/questions/36932/how-can-i-represent-an-enum-in-python    
ErrorLevel = enum('DEBUG', 'INFO', 'WARNING', 'ERROR', 'FATAL', 'FIXLOG')

import os

def process_data(data):
    result = []
    for i in range(len(data)):
        item = data[i]
        if item['status'] == 'active':
            name = item['name']
            value = item['value']
            formatted = str(name) + ': ' + str(value)
            result.append(formatted)
        else:
            pass
    return result

def read_config(path):
    f = open(path, 'r')
    content = f.read()
    f.close()
    return content

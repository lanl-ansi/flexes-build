import os, json

test_commands_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_commands.json')
with open(test_commands_file) as f:
    test_commands = json.load(f)

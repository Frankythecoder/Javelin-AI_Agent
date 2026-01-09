import json
import csv

# Read the JSON data from the file
with open('users.json', 'r') as json_file:
    users = json.load(json_file)

# Convert JSON to CSV
with open('users.csv', 'w', newline='') as csv_file:
    csv_writer = csv.writer(csv_file)
    # Write the header
    csv_writer.writerow(users[0].keys())
    # Write user data
    for user in users:
        csv_writer.writerow(user.values())
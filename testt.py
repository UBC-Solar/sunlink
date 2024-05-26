# # Example dictionary
# display_data = {
#     "ROW": {
#         "Raw Hex": ["0x1A2B3C4D5E6F7A8B9C0D"]
#     },
#     "COL": {
#         "Hex_ID": ["0x1A", "0x2B", "0x3C"],
#         "Source": ["Board 1", "Board 2", "Board 3"],
#         "Class": ["Voltage Sensors Data", "Current Sensors Data", "Temperature Sensors Data"],
#         "Measurement": ["Volt Sensor 1", "Current Sensor 1", "Temp Sensor 1"],
#         "Value": [3.3, 5.0, 27.0],
#         "Timestamp": ["2024-05-10 22:15:37", "2024-05-10 22:15:38", "2024-05-10 22:15:39"]
#     }
# }

# ANSI_BOLD = "\033[1m"
# ANSI_GREEN = "\033[92m" 
# ANSI_EXIT = "\033[0m"

# from beautifultable import BeautifulTable, BTColumnCollection
# import warnings

# warnings.simplefilter(action='ignore', category=FutureWarning)

# # Create a table
# table = BeautifulTable()

# # Set the table title
# table.set_style(BeautifulTable.STYLE_RST)
# table.column_widths = [100]
# table.width_exceed_policy = BeautifulTable.WEP_WRAP

# # Title
# table.rows.append([f"{ANSI_GREEN}{f'CAN'}{ANSI_EXIT}"])

# # Add columns as subtable
# subtable = BeautifulTable()
# subtable.set_style(BeautifulTable.STYLE_MYSQL)

# cols = display_data["COL"]
# subtable.rows.append(cols.keys())
# for i in range(len(list(cols.values())[0])):
#     subtable.rows.append([val[i] for val in cols.values()]) 

# table.rows.append([subtable])

# # Add rows
# rows = display_data["ROW"]
# for row_head, row_data in rows.items():
#     table.rows.append([f"{ANSI_BOLD}{row_head}{ANSI_EXIT}"])
#     table.rows.append(row_data)

# # Add subtable to main table
# print(table)

# import canlib

from test3.test3 import func1

def func2(a):
    return a + 1

def func3(b):
    return func1(func2, b)

print(func3(5))
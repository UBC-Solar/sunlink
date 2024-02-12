string = "12.1"
string2 = "N"x``

try:
    x = float(string2)
    print("string is a float")
except ValueError:
    print("string is not a float")
    x = string2  # Set x to the original value if not a float

print(x)

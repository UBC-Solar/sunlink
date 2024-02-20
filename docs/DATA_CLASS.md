# Multiple Datatype Support

The revised sunlink repository now allows support for new datatypes. Specifically, new message types such as VDS messages can now be seamlessly integrated into sunlink.

## How to Add New Datatypes
This explanation will be broken into two stages. The first is **Creation** and the second is **Connection**.

### Creation

To create a new datatype follow the steps below. **The general idea** is that you will create a new message class using the `TEMPLATE_MESSAGE.py` in `templates/` (see implementations of `CAN_Msg.py`, `GPS_Msg.py`, and `GPS_Msg.py` in `parser/data_classes/` for examples). This involves creating a constructor with the `string` of data as input and it will create the `data` and `type` fields. The `data` field is **especially important** because it is formatted in a way that all other processes of sunlink can understand it (see the `REQUIRED (INFLUX) FIELDS` and `DISPLAY FIELDS` descriptions in the example classes). This class will need to be **connected** to some parts of sunlink to 'let it know there is a new datatype in town'.

1. Locate `TEMPLATE_MESSAGE.py` in `templates/` and make a **copy** of it in the **data_classes** folder.
2. Update the class description (comments before `class` keyword) to match your data type's fields and values.
    - Note you **must** have at least the `REQUIRED (INFLUX) FIELDS` filled so that sunlink can recognize your datatype correctly.
    - You must put your `REQUIRED (INFLUX) FIELDS` data in a list so that `Source`, for example, maps to a list of sources (even if you only have one source). Please see **Note 1** in **Notes** below for details.
3. Your `__init__` constructor should **at least** set the `message`, `data` and `type` fields.
4. Implement the `extract_measurements` method in your class such that it returns a `dictionary` with the `REQUIRED (INFLUX) FIELDS` and the `DISPLAY FIELDS`.
    - For details on `DISPLAY FIELDS` see **Note 2** in **Notes** below.
5. **(OPTIONAL)**. You may also add a random message generator for your data class. To do this open `randomizer.py` inside the `parser` folder and head to the bottom of the file.
6. Implement a method to randomly generate/return a **latin-1 decoded string** which your data class's `extract_measurements` method can recognize and parse.
7. At the top of `randomizer.py` modify the `random_message_str` method to include these things:
    - Add an `elif` statement to check if `message.type` matches your data class' `type` field and if s then return the output of the random message generator you implemented. See **Note 3** in **Notes** for details on how to run the randomizer with your data type.

### Connection
To connect your data class implementation to the rest of `sunlink`, follow the steps below. **The general idea** is that the factory method called `create_message.py` needs to know your data class exists and `parameters.py` needs to know the length of your data class messages and (if necessary) any format specifiers (such as a DBC file for CAN messages). **Note if you want to add a row to the config table to show your new data type's file specifier then you will need to modify the `print_config_table` function in `link_telemetry.py`**.

1. Navigate to `create_message.py` and perform the following modifcation:
    - Import your data class at the top of the file where the other imports are. Ex. ```from parser.data_classes.<CLASS_FILE_NAME_NO_PY> import <CLASS_NAME>```.

2. Add an `elif` for your data class that has the general format:
```python
elif <CLASS_NAME>_LENGTH_MIN <= len(message) <= <CLASS_NAME>_LENGTH_MAX: 
            return <CLASS_NAME>(message)  
```

3. Navigate to `parameters.py` and perform the follow modifiction:
    - To distinguish incoming messages, this implementation **currently** compares the length to the range of possible string lengths for a specifc type of message. As such, add a `MIN` and `MAX` string length.

## Debugging Tips and Tricks
If you are using wsl or some virtual machine **and** editing code on your local computer then you will have to `git push` to your sunlink branch and then pull from your virtual machine. **IN ADDITION** make sure that if you make changes in files other than those in `link_telemetry.py` you will need to perform a `sudo docker compose restart` to re-spin `main.py` in the Docker Container. 

On the other hand, if you working in the same environment as your set-up sunlink repository (probably some Linux distribution) then simply run `sudo docker compose restart` as necessary.

With that aside here is the general workflow to reduce headaches:
1. First make a **small** change that usually is in just one line. Then perform your `git push/push` and `sudo docker compose restart`. 
    - As `sudo docker compose restart` is running (usually takes 10 to 13 seconds for the parser to fully spin up), you can start on your next small change.
    - Once the parser is spun up you can perform whatever testing you intended on doing.
    - Finally, once you go back to programming, repeat the first step of a small change.
2. `JSONDecodeErrors`. You may get these errors when running `./link_telemetry.py <FLAGS AS NEEDED>`. This is a general error that occurs when anything is not working properly in your code. If you were following step one hopefully this is easy to debug. For example, this error **could** mean but is not limited to:
    - Data is incorrectly parsed
    - the `REQUIRED (INFLUX) FIELDS` are not set correctly
    - Any syntax errors anywhere in the program

## Notes
* Note 1: The `REQUIRED (INFLUX) FIELDS` are `"Source"`, `"Class"`, `"Measurement"`, `"Value"`, and `"Timestamp"`. These fields will be accessed to create an `InfluxDB Point` in `main.py`. This will be done by looping through the list and creating a point for each element in each of the `REQUIRED (INFLUX) FIELDS`'s lists.
* Note 2: The `DISPLAY FIELDS` are sent returned by `main.py` back to the `process_response` method in `link_telemetry.py`. The **keys of the fields are column headings** and the **values are the data for each column**. The number of elements in the list is the number of rows in the pretty table that is printed to the console (aside from the column headings row). 
* Note 3: To run the randomizer with your data type, you will need to run `./link_telemetry.py -r <CLASS_NAME>`. Depending on the how many types of `-r <CLASS_NAME` flags you have this will inform the randomizer of the types of messages that should be randomized. Note that the `<CLASS_NAME>` part of the flag is **case insensitive** because all the flags you enter are forced to all caps.

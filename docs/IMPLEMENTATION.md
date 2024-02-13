# Multiple Datatype Support

The revised sunlink repository now allows support for new datatypes. Specifically, new message types such as VDS messages can now be seamlessly integrated into sunlink.

## How to Add New Datatypes

**Throughout this doc we will take VDS messages as an example of a new message data type that could be added.** This explanation will be broken into two stages. The first is **Creation** and the second is **Connection**.

### Creation

To create a new datatype follow the steps below. **The general idea** is that you will create a new message class using the `TEMPLATE_MESSAGE.py` in `templates/` (see implementations of `CAN_Msg.py`, `GPS_Msg.py`, and `GPS_Msg.py` in `parser/` for examples). This involves creating a constructor with the `string` of data as input and it will create the `data` and `type` fields. The `data` field is **especially important** because it is formatted in a way that all other processes of sunlink can understand it (see the `REQUIRED FIELDS` and `DISPLAY FIELDS` descriptions in the example classes). This class will need to be **connected** to some parts of sunlink to 'let it know there is a new datatype in town'.

1. Locate `TEMPLATE_MESSAGE.py` in `templates/` and make a **copy** of it in the **parser** folder.
2. Update the class description (comments before `class` keyword) to match your data type's fields and values.
    - Note you **must** have at least the `REQUIRED FIELDS` filled so that sunlink can recognize your datatype correctly.
    - You must put your `REQUIRED FIELDS` data in a list so that `Source`, for example, maps to a list of sources (even if you only have one source). Please see **Note 1** in **Notes** below for details.
3. Your `__init__` constructor should **at least** set the `message`, `data` and `type` fields.
4. Implement the `extract_measurements` method in your class such that it returns a `dictionary` with the `REQUIRED FIELDS` and the `DISPLAY FIELDS`.
    - For details on `DISPLAY FIELDS` see **Note 2** in **Notes** below.
    - You may optionally implement the `.data()` and `.type()` methods, however, these are currently not used in `sunlink` (we directly access fields of your class).
5. **(OPTIONAL)**. You may also add a random message generator for your data class. To do this open `randomizer.py` inside the `parser` folder and head to the bottom of the file.
6. Implement a method to randomly generate/return a **latin-1 decoded string** which your data class's `extract_measurements` method can recognize and parse.
7. At the top of `randomizer.py` modify the `random_message_str` method to

### Connection

To connect your data class implementaiton to the rest of `sunlink`, follow the steps below. **The general idea** is that the factory method called `create_message.py` needs to know your data class exists

Optionally, you may also add a random message generator for your class in `randomizer.py` and update the `random_message_str` to use your generator (see implementation details in **Notes** below).

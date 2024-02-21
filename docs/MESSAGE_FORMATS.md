# Formats of All Current Message Types

This doc serves to explain how `firmware_v3` is formatting the messages coming over uart so that sunlink knows how to parse them in the `extract_measurements` methods of the data classes.

## CAN

In the `firmware_v3` repository, the `CAN` messages are a `uint8_t` buffer that is 22 bytes in length. The length is comprised of:

-   8-byte timestamp
-   3-byte id: 1 byte for the `'#'` character and 2 bytes for the id
    -   2 bytes is necessary because **non-extended** ids are 11 bits so rounded to the nearest byte is 16 bits or 2 bytes. **SEE PARSER IMPLEMENTATION FOR EXTENDED IDS**
-   8-byte data
-   1-byte data length character
-   1-byte carriage return character
-   1-byte newline character

On the parser side, we randomize CAN messages by doing the following. Note that latin-1 format is used because it can convert 0 to 255 to a **single width** character, whereas as UTF-8 can convert 0 to 127 to a single width character. Characters after this are not always single width.

-   8-byte current timestamp (in seconds as a double) converted to a latin-1 decoded string that is 8 characters long. When parsed this is rounded to 3 decimal places (CAN messages will not be sent at rates higher than 1ms = 0.001s).
-   5-byte id: 1 byte for the `'#'` character and 4 bytes for the random id from the DBC.
    -   **4 bytes is necessary because extended ids are 29 bits so rounded to the nearest byte is 32 bits or 4 bytes.**
-   8-byte data randomly generated as a an integer ranging from 0 to 2^64. This is then converted to a latin-1 decoded string that is 8 characters long.
-   1-byte data length character

**Note: The carriage return and newline characters are not included in the random message generation because they are at the end of the message so they will not be accessed anyways.**

## GPS

In the `firmware_v3` repository, the `GPS` messages are a `uint8_t` buffer that is 200 bytes in length. However, the data does not take up the full length (when mimicking the `firmware_v3` implementation in parser the length is 121 - 125 bytes depending on how many bytes are needed to represent some values). Here is the format (taken from [firmware_v3](https://github.com/UBC-Solar/firmware_v3/blob/9f1f9ed6bac1b2b526bdd6f252fe398fc3428260/components/tel_v2/Core/Src/freertos.c#L653):

```c
    sprintf(nmea_msg.data,
	    "Latitude: %.6f %c, Longitude: %.6f %c, Altitude: %.2f meters, HDOP: %.2f, Satellites: %d, Fix: %d, Time: %s",
	    gps_data->latitude, gps_data->latSide,
	    gps_data->longitude, gps_data->lonSide,
	    gps_data->altitude, gps_data->hdop,
	    gps_data->satelliteCount, gps_data->fix,
	    gps_data->lastMeasure);
```

On the parser side, we randomize the GPS message as follows:

-   Latitude is a random float from -90 to 90 which is then rounded to 6 decimals places and converted to a string (Ex. 1.234567 to "1.234567").
-   Latside is `'S'` if the latitude is negative and `'N'` if the latitude is positive.
-   Longitude is a random float from -180 to 180 which is then rounded to 6 decimals places and converted to a string.
-   Lonside is `'W'` if the longitude is negative and `'E'` if the longitude is positive.
-   Altitude is a random float from 0 to 1000 which is then rounded to 2 decimals places and converted to a string.
-   HDOP is a random float from 0 to 50 which is then rounded to 2 decimals places and converted to a string.
-   Satellite count is a random integer from 0 to 12 which is then converted to a string.
-   Fix is 0 or 1 (random) and then converted to a string.
-   Time is the current time rounded to 1 decimal place (since GPS messages will not be sent at rates higher than 100ms = 0.1s).

## IMU

In `firmware_v3` the IMU messages are a `uint8_t` buffer that is 17 bytes in length. The length is comprised of:

-   8-byte timestamp
-   3-byte id: 1 byte for the `'@'` character, then 1 byte for the type (A or G) and 1 byte for the axis (X, Y, or Z).
-   4-byte data which is Union between a `float` (4 bytes) and a length 4 `uint8_t` buffer. The purpose of the union is to save the `float` value and then access each of the bytes and put them in the IMU buffer to transmit.
-   1-byte carriage return character
-   1-byte newline character

On the parser side, we randomize the IMU message as follows:

-   8-byte current timestamp (in seconds as a double) converted to a latin-1 decoded string that is 8 characters long. When parsed this is rounded to 3 decimal places (IMU messages will not be sent at rates higher than 1ms = 0.001s).
-  3-byte id: 1 byte for the `'@'` character, then 1 byte for the type (random choice between A or G) and 1 byte for the axis (random choice between X, Y, or Z).
-   4-byte data which is a random float from -1000 to 1000 which is converted to a latin-1 string that is 4 characters long.

## NEW MESSAGE TYPE HERE

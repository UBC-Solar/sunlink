# Formats of All Current Message Types
This doc serves to explain how `firmware_v3` is formatting the messages coming over uart so that sunlink knows how to parse them in the `extract_measurements` methods of the data classes.

## CAN
In the `firmware_v3` repository, the `CAN` messages are a `uint8_t` buffer that is `22 
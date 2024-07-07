# How to Setup Tailscale to Access Production Data
During driving sessions we collect millions of CAN messages on the Kvaser Memorator. To view this data we then take the SD card on the Memorator and use the `MemoratorUploader.py` script to upload the data to InfluxDB. However, this data can only be viewed on the computer which it is uploaded on. The problem here is that other teams like **Race Strategy** need to access this data somehow to analyze it and provide an optimal race strategy. To combat this problem we have set up a Tailscale network with Cloudflare tunnelling on the Bay computer which enables other members of the Tailscale network to access this data on `influxdb.telemetry.ubcsolar.com`. Below are the steps to get onto the Tailscale network.

## Windows
1. Navigate to [Tailscale's website to download it for windows](https://tailscale.com/download/windows)
2. Click **Download Tailscale for Windows**
3. Once downloaded run the .exe file
4. Agree to the terms and conditions and click **Install**
5. Now we need to sign into tailscale with GitHub using the solar admin account **(make sure to sign out afterwards**). To do this go to [Tailscale's sign in page](https://www.google.com/url?sa=t&source=web&rct=j&opi=89978449&url=https://login.tailscale.com/start&ved=2ahUKEwiZteTtw5WHAxVgiY4IHYhoAFIQFnoECCEQAQ&usg=AOvVaw1buC-MDlbw2TpOpK4NqiP9)
6. Click **Sign up with GitHub**
7. **Ask Team Lead for Solar Admin Credentials**
8. Once you sign in it will ask for a verification code sent to the `admin@ubcsolar.com` email. Again, **ask Team lead for this verification code.**
9. Enter the code and click **Authorize Tailscale**
10. Then click on **ubcsolar-admin.github**
11. Once you are authorized we need to actually connect your device to the Tailscale network. 
12. Since we are on windows, open **Powershell** as an administrator.
13. Then run `tailscale up`. This will redirect you to a web browser on which it will ask you to select a tailnet. Here, click **ubcsolar-admin.github** and then click **Connect**
14. Then you will need to login to tailscale so like before choose **Sign in with GitHub**
15. Then click **Authorize Tailscale**. Note here you may be asked to select a tailscale network to connect to again so simply select **ubcsolar-admin.github** and then click **Connect**. **Note: pay attention to your device name as it comes up on this screen so you can identify it in the machines tab on tailscale**.
16. Now, on the **Machines** tab of tailscale you should see your device listed. It is recommended to click the 3 dots on the line with your machine name and then select **Edit machine name**. Here unselect **Auto-generate from OS hostname** and enter something suitable and unique. Then click **Update Name**.
17. Now you should be able to access services like `influxdb.telemetry.ubcsolar.com` and `grafana.telemetry.ubcsolar.com`. Make sure to sign in with `admin` and `new_password`.
18. Go back to GitHub and sign out of the solar admin account.'

## Linux (Ubuntu)
Coming soon...

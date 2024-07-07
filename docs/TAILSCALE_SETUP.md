# How to Setup Tailscale to Access Production Data
During driving sessions we collect millions of CAN messages on the Kvaser Memorator. To view this data we then take the SD card on the Memorator and use the `MemoratorUploader.py` script to upload the data to InfluxDB. However, this data can only be viewed on the computer which it is uploaded on. The problem here is that other teams like **Race Strategy** need to access this data somehow to analyze it and provide an optimal race strategy. To combat this problem we have set up a Tailscale network with Cloudflare tunnelling on the Bay computer which enables other members of the Tailscale network to access this data on `influxdb.telemetry.ubcsolar.com`. Below are the steps to get onto the Tailscale network.

## Windows
1. Navigate to [Tailscale's website to download it for **Windows**](https://tailscale.com/download/windows)
2. Click **Download Tailscale for Windows**
3. Once downloaded run the .exe file
4. Agree to the terms and conditions and click **Install**
5. Once Tailscale is installed open **Powershell** as an administrator.
6. Run the command `tailscale up --auth-key <ASK_LEAD_FOR_AUTHKEY>`
7. Now you should be able to access services like `influxdb.telemetry.ubcsolar.com` and `grafana.telemetry.ubcsolar.com`. Make sure to sign in with `admin` and `new_password`.

## Linux (Ubuntu)
1. Navigate to [Tailscale's website to download it for **Linux**](https://tailscale.com/download/linux) to see these same commands under the manual set up instructions.
2. Run `curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null`
3. Then run `curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list`
4. Then run `sudo apt-get update`
5. Then run `sudo apt-get install tailscale`
6. Then run `sudo tailscale up --auth-key <ASK_LEAD_FOR_AUTH_KEY>`
7. Now you should be able to access services like `influxdb.telemetry.ubcsolar.com` and `grafana.telemetry.ubcsolar.com`. Make sure to sign in with `admin` and `new_password`.

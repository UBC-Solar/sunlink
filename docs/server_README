This is the server that hosts the production instance of UBC Solar's telemetry system - Sunlink.

Sunlink is run as a cluster of Docker containers. These have been started in a tmux session. To attach to the tmux session do: `tmux a`. To detach from the tmux session, do: `ctrl+w d`.

The tmux instance has been setup with a custom configuration file located at `~/.tmux.conf`. The most important difference to note is that the prefix has been remapped from `ctrl+b` to `ctrl+w`.

nginx (an HTTP server) has been set up as a reverse proxy to Sunlink's Docker cluster.

- `https://<droplet-ip>/`                       ->      port 3000 on grafana container
- `https://<droplet-ip>:8086/`                  ->      port 8086 on influxdb container
- `http://<droplet-ip>:5000/`                   ->      port 5000 on parser container

NOTE: the parser API uses basic HTTP since HTTPS results in slowdowns on the `link_telemetry.py` side due to the additional overhead of the TLS handshake.

NOTE: A more desirable setup would be to have `http://<droplet-ip>/influxdb` point to InfluxDB but for some reason InfluxDB does not support that. Therefore, we must expose the 8086 and 5000 ports on the this system to provide access to the Influx and parser containers.

You may find the nginx config file for Sunlink at: `/etc/nginx/sites-available/sunlink`.

A firewall (`ufw`) has also been set up. To list out the allowed connections, do: `sudo ufw status`. You'll see that it allows nginx http and https connections, SSH connections, and connections on ports 5000 (for the parser) and 8086 (for influxdb).

HTTPS for Grafana and Influx was set up with Let's Encrypt. The exact guide followed can be found here: https://www.digitalocean.com/community/tutorials/how-to-secure-nginx-with-let-s-encrypt-on-ubuntu-20-04.

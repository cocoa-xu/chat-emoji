# Chat Emoji Cache Server
Cache YouTube chat emojis.

## Usage
```shell
pip3 install -r requirements.txt
sudo cp -a main.py /usr/local/bin/chat-emoji-server.py
sudo chmod +x /usr/local/bin/chat-emoji-server.py
sudo mkdir -p /etc/chat-emoji
sudo cp -a blocking-list.txt /etc/chat-emoji/blocking-list.txt
sudo chmod a+r /etc/chat-emoji/blocking-list.txt

# edit nginx conf
cp -f nginx-example.conf chat-emoji.example.com
sudo cp -a chat-emoji.example.com /etc/nginx/sites-available/

sudo mkdir -p /var/www/chat-emoji
sudo chown -R www-data:www-data /var/www/chat-emoji

sudo cp -a chat-emoji-server.service /etc/systemd/system/chat-emoji-server.service
sudo systemctl daemon-reload
sudo systemctl enable chat-emoji-server
sudo systemctl start chat-emoji-server
```

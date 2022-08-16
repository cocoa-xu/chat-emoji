import argparse
import base64
from datetime import datetime
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from os.path import exists as f_exists
import logging
from pathlib import Path
from pydoc import doc
import time
import requests


def parse_args():
    cwd = Path(os.getcwd()) / 'cache'
    cwd = cwd.resolve()
    parser = argparse.ArgumentParser(description='YouTube Chat Emoji Cache Server.')
    parser.add_argument('--cache-dir', type=str, default=cwd, help='Cache directory')
    parser.add_argument('--blocking-list', type=str, default=None, help='Blocking paths')
    parser.add_argument('--dump-from', type=str, default=None, help='Dump cached file')
    parser.add_argument('--dump-to', type=str, default=None, help='Dump cached file to')
    parser.add_argument('--chat-host', type=str, default='https://yt3.ggpht.com',
                        help='Cache directory')
    parser.add_argument('--host', type=str, default='localhost', help='Server listen host')
    parser.add_argument('--port', type=int, default=12428, help='Server listen port')
    parser.add_argument('--log-level', type=str, default='info', help='log level')
    parser.add_argument('--log-name', type=str, default='chat_emoji_cache_server',
                        help='logger name')

    return parser.parse_args()


def set_logging_level(log_level_str: str, logger_name: str):
    if log_level_str == 'info':
        log_level = logging.INFO
    elif log_level_str == 'debug':
        log_level = logging.DEBUG
    elif log_level_str in ('warn', 'warning'):
        log_level = logging.WARN
    elif log_level_str == 'fatal':
        log_level = logging.FATAL
    logging.basicConfig(level=log_level, format='%(asctime)s [%(levelname)s] %(message)s')
    return logging.getLogger(logger_name)


def dump_single(file_path, to_path):
    output_file_name = f"{file_path.stem}.png"
    if to_path.is_dir():
        to_path = to_path / output_file_name
    output_file = to_path.resolve()
    with open(file_path.resolve(), 'r', encoding='utf-8') as cache_file_f:
        cache_file = json.load(cache_file_f)
        with open(output_file, "wb") as output_f:
            output_f.write(base64.b64decode(cache_file['data']))


def dump(from_path, to_path, blocking_map):
    from_path = Path(from_path)
    to_path = Path(to_path)
    if from_path.is_dir():
        files = from_path.glob('*.json')
        to_path.mkdir(parents=True, exist_ok=True)
        for file in files:
            path = file.stem.decode('utf-8')
            if blocking_map is None or path not in blocking_map:
                dump_single(file, to_path)
    else:
        dump_single(from_path, to_path)


def load_blocking_list(blocking_list_file):
    file = Path(blocking_list_file)
    if file.is_file():
        with open(file.resolve(), 'r', encoding='utf-8') as file_handle:
            blocking_map = {}
            for line in file_handle:
                line = line.strip()
                if len(line) > 0:
                    blocking_map[line] = True
            if len(blocking_map) > 0:
                return blocking_map
    return None


class ChatEmojiCacheHandler(BaseHTTPRequestHandler):
    def __init__(self, cache_dir, chat_host, logger, blocking_map, *args):
        self.cache_dir = cache_dir
        self.chat_host = chat_host
        self.logger = logger
        self.blocking_map = blocking_map
        BaseHTTPRequestHandler.__init__(self, *args)

    def handle_landing(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write("""
        <!DOCTYPE html>
        <html lang="en"><head>
        <meta charset="UTF-8">
        <title>Chat Emoji Caches</title>
        <style>
            #emojis {
                line-height: 0;

                -webkit-column-count: 12;
                -webkit-column-gap:   1em;
                -moz-column-count:    12;
                -moz-column-gap:      1em;
                column-count:         12;
                column-gap:           1em;
                -webkit-perspective:  1;
                margin: auto;
                width: 80%;
            }

            #emojis img {
                display: block;
                width: 100% !important;
                height: auto !important;
                padding-top: 1em;
            }

            @media (max-width: 800px) {
                #photos {
                    -moz-column-count:    12;
                    -webkit-column-count: 12;
                    column-count:         12;
                }
            }
            @media (max-width: 400px) {
                #photos {
                    -moz-column-count:    6;
                    -webkit-column-count: 6;
                    column-count:         6;
                }
            }

            body {
                margin: 0;
                padding: 0;
            }
        </style>
        <body>
            <section id="emojis">
        """.encode('utf-8'))

        files = self.cache_dir.glob('*.json')
        for file in files:
            self.wfile.write('<img src="https://chat-emoji.uwucocoa.moe'.encode('utf-8'))
            self.wfile.write(base64.b64decode(file.stem))
            self.wfile.write('">'.encode('utf-8'))


    def key_to_cache_file(self, key):
        base64_key = base64.b64encode(key.encode('ascii')).decode('ascii')
        return f"{self.cache_dir}/{base64_key}.json"

    def ensure_cache_directory(self):
        if not self.cache_dir.exists():
            self.logger.info("creating cache directory at %s", self.cache_dir.resolve())
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_emoji(self, key, headers, data):
        if self.blocking_map is None or key not in self.blocking_map:
            cache_file = self.key_to_cache_file(key)
            base64_data = base64.b64encode(data).decode('ascii')
            cache = {
                "cache_time": time.time(),
                "headers": {
                    "Content-type": headers["Content-type"]
                },
                "data": base64_data
            }
            json_encoded = json.dumps(cache)
            self.ensure_cache_directory()
            with open(cache_file, "w", encoding='utf-8') as cache_file_f:
                cache_file_f.write(json_encoded)

    def fetch_emoji_local(self, key):
        cache_file = self.key_to_cache_file(key)
        if f_exists(cache_file):
            with open(cache_file, "r", encoding='utf-8') as cache_file_f:
                cache = json.load(cache_file_f)
                return True, cache["headers"], cache["data"], cache["cache_time"]
        return False, None, None, None

    def fetch_emoji(self, key):
        cache_hit, header, data, cache_time = self.fetch_emoji_local(key)
        if cache_hit:
            date_time = datetime.fromtimestamp(cache_time)
            cache_time_str = date_time.strftime("%Y-%m-%d %H:%M:%S")
            self.logger.info("cache hit, key=%s, cache_time=%d, datetime=%s",
                             key, cache_time, cache_time_str)
            return (200, header, base64.b64decode(data))

        url = f"{self.chat_host}{self.path}"
        resp = requests.get(url, verify=True)

        if self.blocking_map is not None and key in self.blocking_map:
            self.logger.info("cache ignore, fetch_url=%s, status_code=%d", url, resp.status_code)
        else:
            self.logger.info("cache miss, fetch_url=%s, status_code=%d", url, resp.status_code)
        if resp.status_code == 200:
            self.cache_emoji(key, resp.headers, resp.content)
        headers = {
            "Content-type": resp.headers["Content-type"]
        }
        return resp.status_code, headers, resp.content

    # pylint: disable=invalid-name
    def do_GET(self):
        if self.path == '/':
            self.handle_landing()
        else:
            status_code, headers, data = self.fetch_emoji(self.path)
            self.send_response(status_code)
            for name in headers:
                self.send_header(name, headers[name])
            self.send_header("Cache-Control", "max-age=604800")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)


# pylint: disable=too-few-public-methods
class ChatEmojiCacheServer:
    def __init__(self, host, port, blocking_map, user_args, logger):
        self.logger = logger
        self.cache_dir = Path(user_args.cache_dir)
        self.chat_host = user_args.chat_host
        self.host = host
        self.port = port
        self.blocking_map = blocking_map

    def serve_forever(self):
        def handler(*args):
            ChatEmojiCacheHandler(self.cache_dir, self.chat_host, self.logger,
                self.blocking_map, *args)
        web_server = HTTPServer((self.host, self.port), handler)
        self.logger.info("server started at http://%s:%s", self.host, self.port)
        try:
            web_server.serve_forever()
        except KeyboardInterrupt:
            pass
        web_server.server_close()


if __name__ == "__main__":
    cli_args = parse_args()
    blocking_map = load_blocking_list(cli_args.blocking_list)
    if cli_args.dump_from and cli_args.dump_to:
        dump(cli_args.dump_from, cli_args.dump_to, blocking_map)
    server = ChatEmojiCacheServer(cli_args.host, cli_args.port, blocking_map,
        cli_args, set_logging_level(cli_args.log_level, cli_args.log_name)
    )
    server.serve_forever()

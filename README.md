# Launcher of QQ Pet Game

A QQ pet game launcher. Runs as an web.py server and explodes http apis.

## requirements
```
pip install pymongo web.py
cp config.tpl.conf config.conf
cp static/game_config_tpl.tpl.json static/game_config_tpl.json
mkdir static/qr_code/
mkdir static/game_config/
```
modify `config.conf` and assign [qqbot]path to your own qq pet game path
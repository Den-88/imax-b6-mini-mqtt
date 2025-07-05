import time
import json
import paho.mqtt.client as mqtt
from b6mini import *
import argparse

# --- НАСТРОЙКИ ---
IMAX_VID = 0x0000; IMAX_PID = 0x0001
BASE_TOPIC = "imax_b6mini/charger"
DISCOVERY_PREFIX = "homeassistant"
DEVICE_UNIQUE_ID = "imax_b6mini"

# --- Глобальные переменные ---
action_params = {"mode": 0, "battery_type": 0, "cells": 1, "current": 1.0, "min_voltage": 3.0}
client = None; charger = None
device_info = {"identifiers": [DEVICE_UNIQUE_ID], "name": "iMAX B6 Mini", "manufacturer": "SkyRC"}
availability_topic = f"{BASE_TOPIC}/availability"

# --- Списки для сопоставления ---
MODES_LIST = ["Зарядка", "Быстрая зарядка", "Разрядка", "Хранение"]
BATT_TYPES_LIST = ["LiPo", "LiIo", "LiFe", "LiHV", "NiMH", "NiCD", "Pb"]

def publish_discovery_configs():
    print("Публикация конфигурации с группировкой...")

    # --- ЕДИНЫЙ СЛОВАРЬ ДЛЯ ВСЕХ СУЩНОСТЕЙ ---
    all_entities = {
        # --- СЕНСОРЫ ---
        "sensor": {
            "state":        {"topic": "status", "name": "Состояние", "icon": "mdi:power-plug"},
            "mah":          {"topic": "status", "name": "Ёмкость", "unit": "мАч", "icon": "mdi:battery-plus-variant"},
            "time_sec":     {"topic": "status", "name": "Время", "unit": "s", "class": "duration"},
            "current":      {"topic": "status", "name": "Ток", "unit": "A", "class": "current"},
            "voltage":      {"topic": "voltage_state", "name": "Напряжение", "unit": "V", "class": "voltage", "attr_topic": f"{BASE_TOPIC}/voltage_attributes", "template": "{{ value_json.voltage }}"},
            "tempInt":      {"topic": "status", "name": "Температура (вн.)", "unit": "°C", "class": "temperature"},
            "tempExt":      {"topic": "status", "name": "Температура (внеш.)", "unit": "°C", "class": "temperature"},
            "impedanceInt": {"topic": "status", "name": "Сопротивление", "unit": "мΩ", "icon": "mdi:omega"},
            # "dev_info":     {"topic": "dev_info", "name": "Прошивка", "icon": "mdi:chip", "template": "SW: {{ value_json.sw_version }} / HW: {{ value_json.hw_version }}", "category": "diagnostic"},
            "timeLimit":    {"topic": "sys_info", "name": "Лимит времени", "unit": "min", "class": "duration", "icon": "mdi:timer-sand", "category": "diagnostic"},
            "capLimit":     {"topic": "sys_info", "name": "Лимит ёмкости", "unit": "мАч", "icon": "mdi:battery-arrow-up", "category": "diagnostic"},
            "inDClow":      {"topic": "sys_info", "name": "Мин. входное напряжение", "unit": "В", "icon": "mdi:power-plug-off", "category": "diagnostic"},
            "tempLimit":    {"topic": "sys_info", "name": "Отсечка по температуре", "unit": "°C", "class": "temperature", "category": "diagnostic"},
            "keyBuzz":      {"topic": "sys_info", "name": "Звук кнопок", "icon": "mdi:bell-ring", "category": "diagnostic"},
            "sysBuzz":      {"topic": "sys_info", "name": "Звук системы", "icon": "mdi:bell-ring", "category": "diagnostic"},
            "cycleTime":    {"topic": "sys_info", "name": "Пауза в цикле", "unit": "min", "class": "duration",  "icon": "mdi:clock-fast", "category": "diagnostic"},
            "timeLimitOn":  {"topic": "sys_info", "name": "Ограничение времени", "icon": "mdi:timer-check-outline", "category": "diagnostic"},
            "capLimitOn":   {"topic": "sys_info", "name": "Ограничение ёмкости", "icon": "mdi:battery-lock", "category": "diagnostic"},
        },
        # --- ЭЛЕМЕНТЫ УПРАВЛЕНИЯ ---
        "select": {
            "action_mode":  {"name": "Режим работы", "icon": "mdi:cog", "command_key": "mode", "options": MODES_LIST},
            "battery_type": {"name": "Тип аккумулятора", "icon": "mdi:battery", "command_key": "battery_type", "options": BATT_TYPES_LIST},
        },
        "number": {
            "cells":        {"name": "Кол-во ячеек", "icon": "mdi:numeric", "command_key": "cells", "min": 1, "max": 6, "step": 1, "mode": "box"},
            # "current":      {"name": "Ток", "icon": "mdi:current-ac", "command_key": "current", "min": 0.1, "max": 6.0, "step": 0.1, "unit": "A", "mode": "slider"},
            "current":      {"name": "Ток", "icon": "mdi:current-ac", "command_key": "current", "min": 0.1, "max": 6.0, "step": 0.1, "unit": "A", "mode": "box"},
            "min_voltage":  {"name": "Напряжение отсечки", "icon": "mdi:battery-minus-variant", "command_key": "min_voltage", "min": 3.0, "max": 4.2, "step": 0.1, "unit": "V", "mode": "box"},
        },
        "button": {
            "start":        {"name": "Старт", "icon": "mdi:play-circle-outline", "payload": "start"},
            "stop":         {"name": "Стоп", "icon": "mdi:stop-circle-outline", "payload": "stop"},
        }
    }

    for component, entities in all_entities.items():
        for key, config in entities.items():
            publish_entity(component, key, config)
    print("Полная конфигурация опубликована.")


def publish_entity(component, key, config):
    """Вспомогательная функция для публикации конфигурации сущности."""
    payload = {"name": config['name'], "unique_id": f"{DEVICE_UNIQUE_ID}_{key}", "device": device_info,
        "availability_topic": availability_topic,
        "payload_available": "online",
        "payload_not_available": "offline"}
    if config.get("category"): payload["entity_category"] = config["category"]
    if config.get("icon"): payload["icon"] = config["icon"]

    if component == "sensor":
        payload["state_topic"] = f"{BASE_TOPIC}/{config['topic']}"
        payload["value_template"] = config.get("template", f"{{{{ value_json.{key} }}}}")
        if config.get("unit"): payload["unit_of_measurement"] = config["unit"]
        if config.get("class"): payload["device_class"] = config["class"]
        if config.get("attr_topic"): payload["json_attributes_topic"] = config["attr_topic"]
    elif component == "button":
        payload["command_topic"] = f"{BASE_TOPIC}/command"
        payload["payload_press"] = json.dumps({"command": config["payload"]})
    else: # select, number
        payload["command_topic"] = f"{BASE_TOPIC}/params/{config['command_key']}/set"
        payload["state_topic"] = f"{BASE_TOPIC}/params/state"
        payload["value_template"] = f"{{{{ value_json.{config['command_key']} }}}}"
        if component == "select": payload["options"] = config["options"]
        else: payload.update({"min": config["min"], "max": config["max"], "step": config["step"], "mode": config.get("mode", "box"), "unit_of_measurement": config.get("unit")})

    client.publish(f"{DISCOVERY_PREFIX}/{component}/{DEVICE_UNIQUE_ID}/{key}/config", json.dumps(payload), retain=True)
    time.sleep(0.02) # Небольшая задержка для стабильности

def on_message(client, userdata, msg):
    """Обрабатывает входящие MQTT сообщения для управления устройством."""
    global action_params
    if msg.topic.endswith("/state"): return
    try:
        payload_str = msg.payload.decode()
        print(f"Получено управляющее сообщение в топик '{msg.topic}': {payload_str}")
        if msg.topic.startswith(f"{BASE_TOPIC}/params/"):
            key = msg.topic.split('/')[-2]
            if key == 'mode':
                action_params[key] = payload_str
            elif key == 'battery_type':
                action_params[key] = payload_str
            else:
                action_params[key] = float(payload_str)
            client.publish(f"{BASE_TOPIC}/params/state", json.dumps(action_params), retain=True)

        elif msg.topic == f"{BASE_TOPIC}/command":
            command = json.loads(payload_str).get("command")
            if command == "stop": charger.stop()
            elif command == "start":
                modes = ["Зарядка", "Разрядка", "Хранение", "Быстрая зарядка"]
                mode = modes.index(action_params['mode'])
                batt_type = BATT_TYPES_LIST.index(action_params['battery_type'])
                cells = int(action_params['cells'])
                current = action_params['current']
                min_voltage = action_params['min_voltage']
                print(f"Выполняется команда СТАРТ для режима {mode} с параметрами: {action_params}")
                if mode in [MODE_CHARGE, MODE_FASTCHARGE]:
                    method = charger.charge if mode == MODE_CHARGE else charger.fastcharge
                    method(batt_type, cells, current, cells * 4.2)
                elif mode == MODE_DISCHARGE:
                    charger.discharge(batt_type, cells, current, cells * min_voltage)
                elif mode == MODE_STORAGE:
                    charger.storage(batt_type, cells, current, cells * 3.8)
    except Exception as e:
        print(f"Ошибка при обработке сообщения: {e}")

def main():
    # Создаем парсер аргументов
    parser = argparse.ArgumentParser(description="iMAX B6 Mini MQTT Bridge")
    parser.add_argument('--broker', required=True, help="MQTT broker address")
    parser.add_argument('--port', type=int, required=True, help="MQTT broker port")
    parser.add_argument('--user', help="MQTT username")
    parser.add_argument('--password', help="MQTT password")
    parser.add_argument('--poll-interval', type=int, required=True, help="Polling interval in seconds")
    parser.add_argument('--reconnect-interval', type=int, required=True, help="MQTT reconnect interval")
    
    # Читаем аргументы, переданные из init.d скрипта
    args = parser.parse_args()
  
    while True:
        try:
            global client, charger
            print("Старт iMAX B6 Mini -> MQTT bridge...")
            charger = B6Mini()
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.on_message = on_message
            if args.user and args.password: client.username_pw_set(args.user, args.password)
            try:
                client.connect(args.broker, args.port, 60)
                client.subscribe(f"{BASE_TOPIC}/command")
                client.subscribe(f"{BASE_TOPIC}/params/#")
                client.loop_start()
                print("MQTT broker успешно подключен.")
            except Exception as e: return print(f"Ошибка подключения к MQTT: {e}")
            publish_discovery_configs()
            action_params['mode'] = "Зарядка"
            action_params['battery_type'] = "LiIo"
            client.publish(f"{BASE_TOPIC}/params/state", json.dumps(action_params), retain=True)
            client.publish(availability_topic, "online", retain=True)
            # try:
            #     dev_info = charger.get_dev_info()
            #     dev_payload = {"sw_version": dev_info.sw_version, "hw_version": dev_info.hw_version}
            #     client.publish(f"{BASE_TOPIC}/dev_info", json.dumps(dev_payload), retain=True)
            #     print(f"Device info published: {dev_payload}")
            # except Exception as e: print(f"Could not get device info: {e}")
            charge_info = charger.get_charge_info() 
            charge_info.time_sec = 0
            while True:
                # 1. Получаем свежие данные
                new_charge_info = charger.get_charge_info()
                if new_charge_info.state_str() == "РАБОТАЕТ":
                    charge_info = new_charge_info
                else:
                    # Обновляем только состояние, а все остальные поля (ток, емкость и т.д.)
                    # остаются от последнего "рабочего" замера.
                    charge_info.state = new_charge_info.state
                    charge_info.current = 0
                    charge_info.impedanceInt = new_charge_info.impedanceInt
                    charge_info.tempInt = 0
                    charge_info.tempExt = 0
                    
                sys_info = charger.get_sys_info()
                status_payload = {"state": charge_info.state_str(), "current": charge_info.current / 1000.0, "mah": charge_info.mah,
                                  "time_sec": charge_info.time_sec, "tempInt": charge_info.tempInt, "tempExt": charge_info.tempExt,
                                  "impedanceInt": charge_info.impedanceInt}
                client.publish(f"{BASE_TOPIC}/status", json.dumps(status_payload), retain=True)
                print(f"Данные опубликованы: {status_payload}")
    
                sys_payload = {"timeLimit": sys_info.timeLimit, "capLimit": sys_info.capLimit, "inDClow": sys_info.inDClow,
                               "tempLimit": sys_info.tempLimit, "cycleTime": sys_info.cycleTime,
                               "keyBuzz": "ВКЛ" if sys_info.keyBuzz else "ВЫКЛ", "sysBuzz": "ВКЛ" if sys_info.sysBuzz else "ВЫКЛ",
                               "timeLimitOn": "ВКЛ" if sys_info.timeLimitOn else "ВЫКЛ", "capLimitOn": "ВКЛ" if sys_info.capLimitOn else "ВЫКЛ"}
                client.publish(f"{BASE_TOPIC}/sys_info", json.dumps(sys_payload), retain=True)
                print(f"Системные данные опубликованы: {sys_payload}")
                current_voltage, current_cells = (charge_info.voltage, charge_info.cells) if charge_info.state_str() == "РАБОТАЕТ" else (sys_info.voltage, sys_info.cells or [])
                if current_voltage is not None:
                    client.publish(f"{BASE_TOPIC}/voltage_state", json.dumps({"voltage": current_voltage}), retain=True)
                    cells_attributes = {f"Ячейка {i+1}": v for i, v in enumerate(current_cells)}
                    client.publish(f"{BASE_TOPIC}/voltage_attributes", json.dumps(cells_attributes), retain=True)
                    print(f"Данные напряжения опубликованы: {current_voltage}V, Cells: {cells_attributes}")
                time.sleep(args.poll_interval)
        except Exception as e:
            if client:
                client.publish(availability_topic, "offline", retain=True)
            print(e)
            print(f"Оибка подключения! Повторная попытка...")
        time.sleep(args.reconnect_interval)

if __name__ == "__main__":
    main()

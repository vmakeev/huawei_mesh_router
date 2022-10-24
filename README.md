# Управление роутерами Huawei WiFi Mesh 3 из Home Assistant

Компонент для Home Assistant, позволяющий управлять роутерами [Huawei WiFi Mesh 3](https://consumer.huawei.com/ru/routers/wifi-mesh3/) через локальную сеть.

**0.7.1**

- включение/отключение NFC
- включение/отключение TWT (снижение энергопотребления устройств Wi-Fi 6 в спящем режиме)
- управление функцией быстрого роуминга (802.11r)
- отслеживание подключенных устройств
- определение конкретного роутера, к которому подключено устройство
- определение параметров подключения устройств (частота, сила сигнала, гостевые и mesh устройства)
- информация об аппаратной версии роутера
- информация о версии прошивки роутера

## Установка

Необходимо скопировать папку `huawei_mesh_router` из [последнего релиза](https://github.com/vmakeev/huawei_mesh_router/releases/latest) в папку `custom_components`, расположенную в папке с конфигурацией Home Assistant, после чего перезапустить Home Assistant.

## Настройка

Конфигурация > [Устройства и службы](https://my.home-assistant.io/redirect/integrations/) > Добавить интеграцию > [Huawei Mesh Router](https://my.home-assistant.io/redirect/config_flow_start/?domain=huawei_mesh_router)

По умолчанию роутеры Huawei WiFi Mesh 3 используют имя пользователя `admin`, хотя оно и не отображается в web-интерфейсе и в мобильном приложении

## Отслеживание устройств

Каждое отслеживаемое устройство предоставляет следующие атрибуты:

| Атрибут | Описание | Только когда подключено |
|---------|----------|-------------------------|
|source_type| всегда `router`| Нет |
|ip| IP-адрес устройства | Да |
|mac|MAC-адрес устройства| Нет |
|host_name| Имя устройства по данным самого устройства| Нет |
|connected_via| Имя роутера, через который выполнено подключение. Для основного роутера - `Huawei Mesh 3` | Да |
|interface_type| Тип интерфейса подключения (например `5GHz`, `LAN` и т.д.)| Да |
|rssi| Сила сигнала для беспроводных подключений| Да |
|is_guest| Является ли устройство подключенным к гостевой сети | Да |
|is_hilink| Подключено ли устройство через HiLink (обычно это другие роутеры)| Да |
|friendly_name| Имя устройства, предоставленное роутером | Нет |

Имена устройств для отслеживания, включая роутеры, могут быть изменены в [интерфейсе управления вашей mesh-системой](http://192.168.3.1/html/index.html#/devicecontrol), после чего компонент обновит их и в Home Assistant


Пример markdown карточки, отображающей часть информации об отслеживаемом устройстве:

```
Мой телефон: Rssi
{{- " **" + state_attr('device_tracker.my_phone', 'rssi') | string }}** *via*
{{- " **" + state_attr('device_tracker.my_phone', 'connected_via') | string }}**
{{- " **(" + state_attr('device_tracker.my_phone', 'interface_type') | string }})**
```

Результат:
Мой телефон: Rssi **30** *via* **Kitchen router** (**5GHz**)

-----

# Control Huawei WiFi Mesh 3 routers from Home Assistant

Home Assistant custom component for control [Huawei WiFi Mesh 3](https://consumer.huawei.com/ru/routers/wifi-mesh3/) routers over LAN.

**0.7.1**

- enable/disable NFC
- enable/disable TWT (reduce power consumption of Wi-Fi 6 devices in sleep mode)
- control of the fast roaming function (802.11r)
- connected devices tracking
- obtaining of the specific router to which the device is connected
- obtaining of device connection parameters (frequency, signal strength, guest and mesh devices)
- hardware version of the router
- firmware version of the router

## Installation

Manually copy `huawei_mesh_router` folder from [latest release](https://github.com/vmakeev/huawei_mesh_router/releases/latest) to `custom_components` folder in your Home Assistant config folder and restart Home Assistant.

## Configuration

Configuration > [Integrations](https://my.home-assistant.io/redirect/integrations/) > Add Integration > [Huawei Mesh Router](https://my.home-assistant.io/redirect/config_flow_start/?domain=huawei_mesh_router)

By default, Huawei WiFi Mesh 3 routers use the username `admin`, although it is not displayed in the web interface and mobile applications.

## Devices tracking

Each tracked device exposes the following attributes:

|    Attribute   |    Description    | Only when connected |
|----------------|-------------------|---------------------|
| source_type    | always `router`   | No |
| ip             | Device IP address | Yes |
| mac            | MAC address of the device | No |
| hostname       | Device name according to the device itself | No |
| connected_via  | The name of the router through which the connection was made. For the primary router - `Huawei Mesh 3` | Yes |
| interface_type | Connection interface type (eg `5GHz`, `LAN`, etc.) | Yes |
| rssi           | Signal strength for wireless connections | Yes |
| is_guest       | Is the device connected to the guest network | Yes |
| is_hilink      | Is the device connected via HiLink (usually other routers) | Yes |
| friendly_name  | Device name provided by the router | No |

Tracked device names, including routers, can be changed in [your mesh control interface](http://192.168.3.1/html/index.html#/devicecontrol), after which the component will update them in Home Assistant

An example of a markdown card that displays some of the information about the tracked device:

```
My phone: Rssi
{{- " **" + state_attr('device_tracker.my_phone', 'rssi') | string }}** *via*
{{- " **" + state_attr('device_tracker.my_phone', 'connected_via') | string }}**
{{- " **(" + state_attr('device_tracker.my_phone', 'interface_type') | string }})**
```

Result:
My phone: Rssi **30** *via* **Kitchen router** (**5GHz**)

# Управление роутерами Huawei WiFi Mesh 3 из Home Assistant

Компонент для Home Assistant, позволяющий управлять роутерами [Huawei WiFi Mesh 3](https://consumer.huawei.com/ru/routers/wifi-mesh3/) через локальную сеть.

**0.7.0**

- включение/отключение NFC
- включение/отключение TWT (снижение энергопотребления устройств Wi-Fi 6 в спящем режиме)
- управление функцией быстрого роуминга (802.11r)
- отслеживание подключенных устройств
- определение конкретного роутера, к которому подключено устройство
- определение параметров подключения устройств (частота, сила сигнала, гостевые и mesh устройства)
- информация об аппаратной версии роутера
- информация о версии прошивки роутера

## Установка

Необходимо скопировать папку `huawei_mesh_router` в папку `custom_components`, расположенную в папке с конфигурацией Home Assistant, после чего перезапустить Home Assistant.

## Настройка

Конфигурация > [Устройства и службы](https://my.home-assistant.io/redirect/integrations/) > Добавить интеграцию > [Huawei Mesh Router](https://my.home-assistant.io/redirect/config_flow_start/?domain=huawei_mesh_router)

По умолчанию роутеры Huawei WiFi Mesh 3 используют имя пользователя `admin`, хотя оно и не отображается в web-интерфейсе и в мобильном приложении
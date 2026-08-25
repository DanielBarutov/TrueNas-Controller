# Публикация полного диска через TrueNAS

## Почему admin station не нужна

Admin station — это Windows-агент для наблюдения за ПК. Она не является
источником образа и не должна быть обязательной для операции на TrueNAS.
Controller UI работает как операторский control plane, а клиентские станции
со свежим heartbeat — как targets.

## Что публикуется

Публикуется весь исходный dataset, например `games/master-games`.
Последовательность должна быть такой:

Перед первым apply в разделе «Станции и агенты» заполните для каждого клиента
точное имя существующего TrueNAS target. Это server-side mapping; агенту и
клиентскому exe API key TrueNAS не передаётся.

1. проверить исходный dataset и отсутствие конфликтующего target;
2. в `dry_run` только показать план;
3. создать snapshot исходного dataset;
4. создать clone snapshot в новый dataset для клиента;
5. найти существующий extent выбранного ПК и заменить его `Device/File` на
   `/dev/zvol/<новый clone>` без создания нового extent и без смены target/LUN;
6. проверить read-back extent/mapping и heartbeat клиента.

Публикация не делит dataset на отдельные игры и не проверяет
`game_version_marker`. Факт готовности образа подтверждает оператор.

## Безопасность

Ключ TrueNAS API остаётся только на backend/worker. Native agent не получает его
и не управляет ZFS напрямую. Реальные snapshot/clone/switch должны выполняться
только после отдельного apply-разрешения; старые clones и mappings не удаляются
автоматически.

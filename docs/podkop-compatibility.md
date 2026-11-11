# Проверка совместимости с Podkop 0.7.22

Дата исследования: 2026-11-11. Изучены [документация](https://podkop.net/), [секции](https://podkop.net/docs/sections/), [настройки](https://podkop.net/docs/settings/) и локальная копия официального tag `0.7.22`, commit `c0a2736bb95884c19fedf638345ed6148c5fd6af`. При расхождениях приоритет у этого tag. Сторонние списки правил не импортировались.

| Вопрос | Подтверждённое поведение |
|---|---|
| Форматы | Удалённые `.json` — source rule-set sing-box, `.srs` — binary rule-set; остальные расширения, включая `.txt`, — plain text. JSON — именно схема sing-box, не произвольный массив. |
| Домены | `remote_domain_lists`, отдельный DynamicList в секции LuCI. Plain text импортируется в `domain_suffix`. |
| Подсети | `remote_subnet_lists`, отдельный DynamicList. Plain text импортируется в `ip_cidr` и IPv4-набор nftables. |
| Поддомены | Bare `telegram.org` покрывает сам домен и поддомены. `*.` не нужен. |
| Пустые строки | Импортёр пропускает пустые строки и обрезает крайние пробелы. Проект публикует более строгий формат. |
| Комментарии | Plain-file импортёр не имеет специального синтаксиса комментариев: строка `#...` невалидна и пропускается; inline-комментарий делает всю запись невалидной. Обработка `//` есть у текстового поля, её нельзя переносить на удалённые файлы. Публикуемые файлы комментариев не содержат. |
| IPv6 | Plain-subnet импортёр проверяет только `is_ipv4`/`is_ipv4_cidr`; nft-набор имеет `type ipv4_addr`. Полноценная маршрутизация IPv6 этим путём не подтверждена и не поддерживается проектом, даже если sing-box сам умеет IPv6. |
| Обновление | `update_interval`: `1h`, `3h`, `12h`, `1d`, `3d`; cron вызывает `/usr/bin/podkop list_update`. JSON/SRS имеют отдельный remote ruleset в sing-box с интервалом. |
| Прямой IP | Доменного DNS/FakeIP-совпадения может не быть. Для IPv4 нужен подтверждённый CIDR в списке подсетей, попадающий и в nft-набор перехвата. |
| Один смешанный файл | Для plain text использовать нельзя: разные обработчики принимают только свой тип. JSON/SRS технически могут содержать разные правила, но DNS/FakeIP и nft-путь различаются; проект всегда разделяет домены и подсети. |
| sing-box | Требуется совместимая версия; release 0.7.22 проверяет минимум 1.12.4. Поддержка движком формата не означает поддержку всей цепочкой Podkop/nftables. UDP зависит от outbound и сервера. |

Точные ссылки на исходники:

- [rulesets.sh](https://github.com/itdoginfo/podkop/blob/0.7.22/podkop/files/usr/lib/rulesets.sh): `import_plain_domain_list_to_local_source_ruleset_chunked`, `import_plain_subnet_list_to_local_source_ruleset_chunked`, выбор формата.
- [helpers.sh](https://github.com/itdoginfo/podkop/blob/0.7.22/podkop/files/usr/lib/helpers.sh): проверки IPv4 и доменов, различие string/file-парсеров.
- [nft.sh](https://github.com/itdoginfo/podkop/blob/0.7.22/podkop/files/usr/lib/nft.sh): `nft_create_ipv4_set`, IPv4-фильтр при загрузке элементов.
- [podkop](https://github.com/itdoginfo/podkop/blob/0.7.22/podkop/files/usr/bin/podkop): обработчики remote-list, `add_cron_job`, `list_update`, проверка непустой загрузки.
- [section.js](https://github.com/itdoginfo/podkop/blob/0.7.22/luci-app-podkop/htdocs/luci-static/resources/view/podkop/section.js): `remote_domain_lists` и `remote_subnet_lists`.
- [settings.js](https://github.com/itdoginfo/podkop/blob/0.7.22/luci-app-podkop/htdocs/luci-static/resources/view/podkop/settings.js): `update_interval`.
- [русская локализация](https://github.com/itdoginfo/podkop/blob/0.7.22/luci-app-podkop/po/ru/podkop.po): точные подписи полей LuCI.

Полностью пустую удалённую загрузку Podkop отвергает: HTTP 200 пустого файла ещё не означает успешный импорт. После изменений проверяйте реальные rule-set и журнал. Проект не запускал Podkop/sing-box на роутере и не подтверждает версию OpenWrt пользователя как протестированную платформу.

# Spotify

Проверка 12 ноября 2026 года. Добавлены 3 домена и 12 IPv4 `/32`, оба списка сопровождаются вручную. Это снимок подтверждённых endpoint, а не гарантия полного покрытия или стабильности IP. Настройки Podkop, DNS, VPN и sing-box не менялись.

## Домены и источники

- `spotify.com`: сайт, `open.spotify.com`, авторизация `accounts.spotify.com`, API и региональные точки подключения. [Документация Web API](https://developer.spotify.com/documentation/web-api/reference/get-track), [авторизация](https://developer.spotify.com/documentation/web-api/concepts/authorization).
- `scdn.co`: в официальном примере ответа API используется `i.scdn.co` для обложек. Корневой домен включает другие поддомены CDN.
- `spotifycdn.com`: HTML официальной API-документации загружает ресурсы с `developer-assets.spotifycdn.com`; корневой домен включает другие CDN-поддомены. Это подтверждение использования домена Spotify, а не проверка каждого медиаузла.

Bare domain включает поддомены по `domain_suffix`. Список распространяется на web, desktop, mobile и устройства Connect при обработке их трафика роутером, но реальная работа этих клиентов не тестировалась. Доставка всего аудио, видео, Canvas, подкастов и lossless не подтверждена. Общие корни `akamaized.net`, `akadns.net`, CloudFront и сети облачных провайдеров не добавлены. Для дополнительных конкретных медиаузлов нужны первичные данные из клиента или официальных материалов.

## Основание IP-списка

1. Выполнен HTTPS-запрос к [официальному resolver Spotify](https://apresolve.spotify.com/?type=accesspoint&type=dealer&type=spclient). Он вернул имена `accesspoint`, `dealer` и `spclient` кластеров `gew1`, `guc3`, `gue1`, `gae2`.
2. Для каждого выданного имени выполнен отдельный DNS A-запрос через HTTPS Google Public DNS. Google — независимый DNS-сервис, не официальный источник IP-диапазонов Spotify. В `sources/sources.json` результаты имеют `trust: primary-research`, а не `official`.
3. Включены только точные публичные IPv4 `/32`, связанные с endpoint resolver. [Снимок ответа, CNAME, A и TTL](../sources/spotify-endpoints.json) сохраняет основание каждой записи. ASN/WHOIS и принадлежность облаку не использованы для расширения сетей.

| Узел | IPv4 |
|---|---|
| ap-gae2.spotify.com | 104.199.241.202 |
| ap-gew1.spotify.com | 104.199.65.9 |
| ap-guc3.spotify.com | 104.154.127.247 |
| ap-gue1.spotify.com | 34.158.255.62 |
| gae2-dealer.spotify.com | 35.186.224.35 |
| gae2-spclient.spotify.com | 35.186.224.22 |
| gew1-dealer.spotify.com | 35.186.224.33 |
| gew1-spclient.spotify.com | 35.186.224.26 |
| guc3-dealer.spotify.com | 35.186.224.36 |
| guc3-spclient.spotify.com | 35.186.224.31 |
| gue1-dealer.spotify.com | 35.186.224.38 |
| gue1-spclient.spotify.com | 35.186.224.9 |

DNS подтверждает разрешение выданного Spotify имени в момент проверки. Он не доказывает исключительное использование адреса Spotify. IP-маршрут может направить через VPN другие приложения на том же IP. Это не перечень всех сетей Spotify, не список адресов медиадоставки и не наблюдение реальных сессий пользователя. Выбор узлов зависит от региона, времени и запроса resolver; уже при двух запросах состав кластеров различался. DNS TTL короткие, адреса могут измениться после проверки. Удаление прежних записей при будущем обновлении требует отдельного подтверждения устаревания.

Автообновление выключено: действующий updater поддерживает только CIDR-feed, а resolver выдаёт JSON с именами узлов. Новый парсер не добавлен. IPv6 не опубликован для совместимости с Podkop 0.7.22; отсутствие IPv6-адресов в файле не означает отсутствия IPv6 у сервиса.

## Транспорт и диагностика

Resolver объявил порты accesspoint `4070`, `443`, `80`; dealer/spclient — `443`. [Официальная документация Sonos](https://support.sonos.com/en/article/configure-your-firewall-to-work-with-sonos) независимо указывает TCP 4070 и UDP 5353 для Spotify Connect. Это документация интеграции Sonos, не самой Spotify; UDP 5353 относится к локальному обнаружению. [Spotify Connect](https://support.spotify.com/us/article/spotify-connect/) требует одну Wi-Fi сеть при первом подключении колонки. LAN multicast и локальные адреса в VPN-списки не включены. Универсальный перечень TCP/UDP для всех клиентов, включая QUIC, не установлен.

Проверяйте отдельно вход, поиск, начало и перемотку трека, обложки, подкасты, видео и Connect. При сбое соберите имена и реальные назначения соединений клиента; не добавляйте целую сеть CDN. На машине исследования системный DNS возвращал `198.18.0.0/15` fake-IP: они отклонены, использован публичный DNS-over-HTTPS. Учитывайте такую подмену при будущих захватах.

`open.spotify.com` и `www.spotify.com` при прямой загрузке из исследовательского окружения вернули HTTP 403; HTML официальной API-документации и HTTPS resolver были доступны. Две страницы Commercial Hardware requirements не удалось открыть веб-инструментом; они не использованы как подтверждение. Воспроизведение, TLS/TCP-сессии к перечисленным IP, реальный маршрут через роутер, GitHub Actions и новые Raw URL не проверялись.

## Публикация

После просмотра diff, если публикация разрешена, из корня проекта:

```sh
git add services.json sources/sources.json sources/spotify-endpoints.json domains/spotify.txt subnets/spotify.txt domains/all.txt subnets/all.txt README.md docs/spotify.md docs/verification.md
git commit -m "feat: add Spotify domain and IPv4 endpoint lists"
git push origin main
```

В текущем изменении commit/push не выполнялись. URL из README соответствуют существующему remote, доступность новых файлов после публикации нужно проверить отдельно.

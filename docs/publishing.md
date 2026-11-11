# Публикация

В этом окружении GitHub CLI (`gh`) не найден. Локальный проект подготовлен; владелец GitHub не установлен. Имя из `git config` не является подтверждением логина GitHub. URL с `OWNER` — шаблоны, пока репозиторий не опубликован.

После установки GitHub CLI и авторизации выполните в корне проекта:

```sh
gh auth login
gh auth status
gh api user --jq .login
gh repo view OWNER/podkop-rules
```

Замените `OWNER` проверенным логином. Если `repo view` завершился ошибкой, сначала отличите отсутствие репозитория от проблем авторизации/сети. Если репозиторий существует, проверьте его содержимое и историю; не используйте дальнейшую команду создания и не перезаписывайте remote без проверки. Для существующего содержимого подготовьте обычный PR из совместимой истории.

Для **подтверждённо отсутствующего** репозитория:

```sh
python -m unittest discover -s tests -v
python scripts/validate_lists.py
python scripts/build_lists.py --check
git status
gh repo create OWNER/podkop-rules --public --source . --remote origin --push
gh workflow run validate.yml --ref main
gh workflow run update.yml --ref main
gh run list --limit 10
```

Изначальный commit уже подготовлен локально; если его нет, перед созданием remote выполните `git add` только файлов проекта и `git commit -m "feat: initialize Podkop routing lists"`. Не включайте `.research/`, `.cache/`, `.env`, pcap или приватные настройки. После дальнейших изменений используйте обычный push; force push не нужен.

В `gh run list` найдите ID обоих запусков, затем проверьте каждый:

```sh
gh run watch RUN_ID --exit-status
gh run view RUN_ID --log-failed
```

Проверьте все восемь файлов. Пример PowerShell после замены владельца:

```powershell
$rulesOwner = 'OWNER'
$rulesBase = "https://raw.githubusercontent.com/$rulesOwner/podkop-rules/main"
foreach ($rulesKind in @('domains', 'subnets')) {
    foreach ($rulesService in @('all', 'telegram', 'twitch', 'albion')) {
        $rulesUrl = "$rulesBase/$rulesKind/$rulesService.txt"
        $rulesResponse = Invoke-WebRequest -Uri $rulesUrl -UseBasicParsing
        [PSCustomObject]@{ Url = $rulesUrl; Status = $rulesResponse.StatusCode; Bytes = $rulesResponse.RawContentLength }
    }
}
```

Ожидается HTTP 200 для каждого файла; ноль байт у подсетей Twitch/Albion — ожидаемо. Дополнительно сравните тело непустых ответов с локальными файлами. GitHub Raw может кэшировать предыдущую версию; при расхождении проверьте commit и повторите позже. Пустые списки не подключайте к Podkop.

После успешной публикации замените шаблоны README фактическими URL, обновите `docs/verification.md` ссылками запусков, статусами и датой проверки. Перепроверьте разрешение Actions на запись и ограничения основной ветки. Никогда не обходите её защиту автоматически.

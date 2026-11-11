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

Проверьте общие файлы и только зарегистрированные сервисные списки. Пример PowerShell после замены владельца:

```powershell
$rulesOwner = 'OWNER'
$rulesBase = "https://raw.githubusercontent.com/$rulesOwner/podkop-rules/main"
$rulesRegistry = Get-Content -LiteralPath services.json -Raw | ConvertFrom-Json
$rulesPaths = @('domains/all.txt', 'subnets/all.txt')
foreach ($rulesService in $rulesRegistry.services.PSObject.Properties) {
    $rulesPaths += $rulesService.Value.domains
    if ($rulesService.Value.PSObject.Properties.Name -contains 'subnets') {
        $rulesPaths += $rulesService.Value.subnets
    }
}
foreach ($rulesPath in $rulesPaths) {
    $rulesUrl = "$rulesBase/$rulesPath"
    $rulesResponse = Invoke-WebRequest -Uri $rulesUrl -UseBasicParsing
    [PSCustomObject]@{ Url = $rulesUrl; Status = $rulesResponse.StatusCode; Bytes = $rulesResponse.RawContentLength }
}
```

Ожидается HTTP 200 для каждого зарегистрированного файла. У Twitch IP-список не зарегистрирован, такого файла и ссылки быть не должно. IP-список Albion зарегистрирован после отдельного запроса пользователя и включается в проверку. Дополнительно сравните тело ответов с локальными файлами. GitHub Raw может кэшировать предыдущую версию; при расхождении проверьте commit и повторите позже. Пустой общий файл возможен, если нет включённых IP-списков; подключать его к Podkop не нужно.

После успешной публикации замените шаблоны README фактическими URL, обновите `docs/verification.md` ссылками запусков, статусами и датой проверки. Перепроверьте разрешение Actions на запись и ограничения основной ветки. Никогда не обходите её защиту автоматически.

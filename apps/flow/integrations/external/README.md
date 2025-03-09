Для работы с сервисом КЦМР нужны сертификаты key и crt
Экспорт ключа выдает в .p12 формате. Для этого необходимо перевести RSA.p12 в key и crt. 

Необходимо ввести пароль:
```shell
openssl pkcs12 -in RSA.p12 -clcerts -nokeys -out kisc.crt
openssl pkcs12 -in RSA.p12 -nocerts -out kisc.key
```

Избавляемся от пароля:
```shell
openssl rsa -in kisc.key -out kisc-wo-pw.key
```

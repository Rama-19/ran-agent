---
name: weather
description: 这是一个天气技能，用于查询天气
metadata: '{"openclaw": {"always": true}}'
---

# Weather

## 获取所在位置的天气

获取你所在位置的天气（[http://wttr.in](https://link.zhihu.com/?target=http%3A//wttr.in) 会根据你的 IP 地址猜测你的位置）：

```shell
curl wttr.in
```

一般返回：

StatusCode        : 200
StatusDescription : OK
Content           : Weather report: not found

​                      \   /     Clear
​                       .-.      11 °C
​                    ― (   ) ―   ↘ 8 km/h    ...

RawContent        : HTTP/1.1 200 OK
                    Access-Control-Allow-Origin: *
                    Content-Length: 8527
                    Content-Type: text/plain; charset=utf-8
                    Date: Mon, 16 Mar 2026 06:06:26 GMT

​                Weather report: not found

​                      \   /...

通过在 `curl` 之后添加 `-4`，强制 cURL 将名称解析为 IPv4 地址（如果你用 IPv6 访问 wttr.in 有问题）：

```shell
curl -4 wttr.in
```

如果你想检索天气预报保存为 png，**还可以使用 Wget**（而不是 cURL），或者你想这样使用它：

​	

```shell
wget -O- -q wttr.in
```

如果相对 cURL 你更喜欢 Wget ，可以在下面的所有命令中用 `wget -O- -q` 替换 `curl`。

指定位置：

```shell
curl wttr.in/Dublin
```

显示地标的天气信息（本例中为艾菲尔铁塔）：

```shell
curl wttr.in/~Eiffel+Tower
```

使用 Wget 将当前天气和 3 天预报下载为 PNG 图像：

```shell
wget wttr.in/weather.png
```


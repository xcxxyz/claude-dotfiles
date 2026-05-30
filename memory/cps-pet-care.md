---
name: cps-pet-care
description: CPS智能宠物看护系统 — ESP32仿真(Wokwi) + 华为云IoTDA MQTT + 微信小程序
metadata: 
  node_type: memory
  type: project
  originSessionId: 2b311dec-eaf8-4bdd-bb84-ba0b01f0a0fb
---

## 架构
Wokwi ESP32 → MQTT → 华为云 IoTDA → MQTT/WebSocket → 微信小程序

## 四个功能模块
1. **环境舒适度调节** — DHT22 + LDR → LED PWM 自动调节，阈值可远程修改
2. **宠物健康监测** — 模拟心率(80±random) → 云端显示 + 每日曲线
3. **活动次数统计** — PIR → 活动计数 → 云端统计 + 页面曲线
4. **云端定时喂食** — 小程序设置时间 → MQTT 下发指令 → 舵机执行

## 华为云连接
- Host: 49263b4a1c.st1.iotda-device.cn-north-4.myhuaweicloud.com
- Port: 8883 (mqtts)
- Device ID: 69fc054c7f2e6c302f6e5dfd_pet_0

## Wokwi 引脚 (用户正确接线)
DHT22 SDA → D27, 舵机 → D16, LED(220Ω) → D25, 光敏 AO → D33, PIR OUT → D26

## 待完成
- [ ] sketch.ino 加 MQTT
- [ ] 小程序改 MQTT 直连
- [ ] data 页面图表
- [ ] control 页面 LED+喂食
- [ ] settings 阈值修改

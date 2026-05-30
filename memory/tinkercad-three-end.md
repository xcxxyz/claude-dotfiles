---
name: tinkercad-three-end
description: 三端IoT — Tinkercad Arduino + Node.js桥接 + 微信小程序/Web + 华为云IoTDA
metadata: 
  node_type: memory
  type: project
  originSessionId: 2b311dec-eaf8-4bdd-bb84-ba0b01f0a0fb
---

## 结构
- Tinkercad: Arduino Uno + 光敏传感器 + LED (PWM调光)
- Node.js bridge (`bridge.js`): 串口读取光敏数据 → 华为云IoTDA MQTT上报 → WebSocket服务(localhost:3000)
- 前端: 微信小程序 + Web移动端，实时LED调光控制
- 设计文档: `docs/superpowers/three-end-iot-design.md`
- 实施计划: `docs/superpowers/three-end-iot-plan.md`

## 技术栈
- 硬件仿真: Tinkercad Circuits
- 云平台: 华为云 IoTDA (MQTT协议)
- 后端: Node.js + serialport + mqtt + ws
- 前端: 微信小程序 + Web (WebSocket实时通信)

**Why:** 物联网课程三端联动实验

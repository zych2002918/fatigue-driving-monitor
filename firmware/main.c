/*
 * firmware/main.c
 * ------------------------------------------------------------------
 * STC89C52 固件参考实现（对照论文第三章硬件设计）。
 *
 * 说明：原竞赛作品为硬件实物（STC89C52 + GY-25 姿态传感器 +
 * 薄膜压力传感器 + LCD1602 + ISD1820 语音 + 蜂鸣器/继电器风扇）。
 * 本目录提供"忠实于论文逻辑"的 8051 C 参考代码，便于移植到
 * 51 开发板复现硬件通道。本项目默认在 PC 上用 SimulatedBehavior
 * 软件模拟该行为通道（见 fatigue/behavior.py），故固件仅供参考，
 * 不参与默认构建。
 *
 * 论文 3.2.7 执行逻辑：
 *   1) 无握力 -> 蜂鸣 + 风扇（立即）
 *   2) 有握力但 3 秒内无转角 -> 蜂鸣；30 秒超时 -> 加风扇
 *   3) 累计驾驶时长达阈值 -> 语音"当前处于疲劳驾驶，请停车休息"
 *      + 蜂鸣 + 风扇
 *
 * 硬件映射（论文）：
 *   压力传感器 -> P1.3（无压力高电平，受压低电平）
 *   GY-25      -> 串口 P3.0(RXD)/P3.1(TXD) 或 I2C
 *   继电器风扇 -> P2.1 低电平驱动
 *   蜂鸣器     -> P2.2 低电平驱动
 *   LCD1602    -> I2C
 *   ISD1820    -> GPIO (PLAYE/PLAYL)
 */

#include <reg52.h>
#include <stdio.h>

/* ---- 引脚定义（按论文 3.2） ---- */
sbit PRESS = P1 ^ 3;   /* 薄膜压力传感器输入：0=有握力 1=无握力 */
sbit RELAY_FAN = P2 ^ 1;  /* 继电器风扇：0=吸合(开) */
sbit BUZZER = P2 ^ 2;     /* 蜂鸣器：0=响 */
sbit VOICE_PLAY = P3 ^ 7; /* ISD1820 PLAY 触发 */

/* ---- 时间常量（论文） ---- */
#define NO_STEER_BUZZ_S 3   /* 有握力无转角 3s -> 蜂鸣 */
#define NO_STEER_FAN_S 30   /* 无转角 30s -> 风扇 */
#define DRIVE_LIMIT_S 7200L /* 驾驶时长阈值(2h) */

/* ---- 状态 ---- */
static unsigned char hands_on = 1;
static unsigned char steer_changed = 0;
static unsigned long timer0_cnt = 0;   /* 10ms 计数 */
static unsigned long drive_seconds = 0;
static unsigned long no_steer_seconds = 0;
static unsigned long last_steer_seconds = 0;

void delay10ms(unsigned int n);
void lcd_show(unsigned char line, unsigned char *str);
void voice_say_rest(void);

/* 定时器0：10ms 中断，做秒表与时序 */
void timer0_isr(void) interrupt 1
{
    TH0 = 0xDC;
    TL0 = 0x00;   /* 10ms @12MHz */
    timer0_cnt++;
    if (timer0_cnt >= 100) {   /* 1s */
        timer0_cnt = 0;
        drive_seconds++;
        no_steer_seconds = drive_seconds - last_steer_seconds;
    }
}

/* 模拟：读取 GY-25（此处示意；真实需串口协议 A4 03 14 08 ...） */
static unsigned char read_steer_change(void)
{
    /* 返回 1 表示检测到转角变化（由外部串口解析填充） */
    return 0;
}

void main(void)
{
    unsigned char alarm = 0;
    /* 初始化 */
    TMOD = 0x01;        /* T0 方式1 */
    TH0 = 0xDC; TL0 = 0x00;
    ET0 = 1; EA = 1; TR0 = 1;

    while (1) {
        /* 1) 读取压力传感器：无握力 -> 3 级 */
        hands_on = PRESS ? 0 : 1;
        if (!hands_on) {
            alarm = 3;
            RELAY_FAN = 0;   /* 风扇开 */
            BUZZER = 0;      /* 蜂鸣 */
        } else {
            /* 2) 转角变化检测（由串口中断填充标志） */
            if (read_steer_change()) {
                last_steer_seconds = drive_seconds;
            }
            if (no_steer_seconds >= NO_STEER_FAN_S) {
                alarm = 3;
                RELAY_FAN = 0;
                BUZZER = 0;
            } else if (no_steer_seconds >= NO_STEER_BUZZ_S) {
                alarm = 2;
                BUZZER = 0;    /* 仅蜂鸣 */
                RELAY_FAN = 1;
            } else {
                alarm = 0;
                BUZZER = 1;
                RELAY_FAN = 1;
            }
        }
        /* 3) 驾驶时长超限 */
        if (drive_seconds >= DRIVE_LIMIT_S) {
            alarm = 3;
            BUZZER = 0;
            RELAY_FAN = 0;
            voice_say_rest();
        }
        /* LCD 刷新（示意） */
        /* lcd_show(0, "T:xxxx s"); */
        delay10ms(10);
    }
}

void delay10ms(unsigned int n)
{
    unsigned int i, j;
    for (i = 0; i < n; i++)
        for (j = 0; j < 1200; j++);
}

/* 语音播报（示意：触发 ISD1820 PLAYL） */
void voice_say_rest(void)
{
    VOICE_PLAY = 1;
    delay10ms(3);
    VOICE_PLAY = 0;
}

/* LCD 留空实现：接入 HD44780/I2C 后填充 */
void lcd_show(unsigned char line, unsigned char *str)
{
    (void)line; (void)str;
}

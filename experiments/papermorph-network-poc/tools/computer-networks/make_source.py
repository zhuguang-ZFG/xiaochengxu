from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "books" / "computer-networks" / "book.pdf"

CHAPTERS = [
    (1, "第一章 计算机网络与链路时延"),
    (2, "第二章 存储转发：一跳一跳地等"),
    (3, "第三章 可靠传输：丢了怎么办"),
]

PAGES = [
    (
        "第一章 计算机网络与链路时延",
        [
            "原创教学源稿，不是任何教材的副本。",
            "学习目标：",
            "1. 区分链路速率、传输时延与传播时延。",
            "2. 根据数据包大小和链路速率计算传输时延。",
            "3. 在忽略排队和处理时延的简化模型中计算总时延。",
            "4. 改变链路速率，观察发送时间与总时延如何变化。",
            "本章假设：数据包大小为 1500 字节，传播时延固定为 10 毫秒。",
        ],
    ),
    (
        "1.1 链路速率与传输时延",
        [
            "链路速率表示每秒可以发送多少比特，常用单位是比特每秒。",
            "1 字节等于 8 比特。1500 字节的数据包等于 12000 比特。",
            "传输时延是发送器把数据包的全部比特推上链路所需的时间。",
            "计算公式：传输时延 = 数据包比特数 ÷ 链路速率。",
            "若速率用兆比特每秒表示，则 12000 ÷ 速率数值就是毫秒数。",
            "例如：10 Mbps 时，传输时延 = 12000 ÷ 10 = 1.2 毫秒。",
            "关键关系：数据包不变时，链路速率越大，传输时延越短。",
        ],
    ),
    (
        "1.2 传播时延与简化总时延",
        [
            "传播时延是一个比特从链路一端传播到另一端所需的时间。",
            "它与链路速率不是同一件事。距离和传播介质会影响传播时延。",
            "本章把传播时延固定为 10 毫秒，不讨论距离变化。",
            "简化总时延 = 传输时延 + 传播时延。",
            "本章忽略排队时延、处理时延和其他协议开销。",
            "因此，10 Mbps 时总时延 = 1.2 + 10 = 11.2 毫秒。",
            "总时延不会低于固定的 10 毫秒传播时间；速率再高，也只能让传输部分趋近于零。",
        ],
    ),
    (
        "1.3 算例与练习",
        [
            "固定数据包为 1500 字节，传播时延为 10 毫秒。",
            "1 Mbps：传输 12.0 毫秒，总时延 22.0 毫秒。",
            "5 Mbps：传输 2.4 毫秒，总时延 12.4 毫秒。",
            "10 Mbps：传输 1.2 毫秒，总时延 11.2 毫秒。",
            "20 Mbps：传输 0.6 毫秒，总时延 10.6 毫秒。",
            "100 Mbps：传输 0.12 毫秒，总时延 10.12 毫秒。",
            "练习：把链路速率调到 10 Mbps，读出传输时延和总时延。",
            "思考：速率从 10 Mbps 提高到 100 Mbps，总时延为什么没有降低十倍？",
        ],
    ),
    (
        "第二章 存储转发：一跳一跳地等",
        [
            "原创教学源稿，不是任何教材的副本。",
            "学习目标：",
            "1. 说明路由器为什么先收完整包，再往下一跳发送。",
            "2. 分别计算一跳的传输时延和传播时延。",
            "3. 在简化模型中计算三跳总时延。",
            "4. 改变三段链路共用速率，观察总时延变化。",
            "假设：1500 字节，即 12000 比特；三段传播各固定 2 毫秒；忽略排队和处理。",
        ],
    ),
    (
        "2.1 先看一跳",
        [
            "传输时延 = 数据包比特数 ÷ 链路速率。",
            "若速率 R 用 Mbps 表示，则 R Mbps = R × 1000 bit/ms。",
            "因此传输时延 = 12000 ÷ (R × 1000) = 12/R 毫秒。",
            "每段传播时延固定为 2 毫秒，所以一跳时间 = 12/R + 2 毫秒。",
            "例如 R = 10 Mbps：传输 1.2 毫秒，传播 2.0 毫秒。",
            "这一跳共用 3.2 毫秒。",
            "关键：速率只改变发送部分，不改变本例固定的传播部分。",
        ],
    ),
    (
        "2.2 存储转发与三跳总时延",
        [
            "路由器必须收到完整数据包，才能把它送上下一段链路。",
            "第一段：发送 1.2 毫秒，传播 2.0 毫秒。",
            "第二段：再发送 1.2 毫秒，再传播 2.0 毫秒。",
            "第三段：再发送 1.2 毫秒，再传播 2.0 毫秒。",
            "10 Mbps 时，总时延 = 3 × 3.2 = 9.6 毫秒。",
            "一般公式：总时延 = 3 × (12/R + 2) = 36/R + 6 毫秒。",
            "传播部分合计固定为 6 毫秒，因此总时延不会低于 6 毫秒。",
        ],
    ),
    (
        "2.3 算例与练习",
        [
            "固定数据包 12000 bit，每段传播 2 ms。",
            "1 Mbps：传输 12.0 ms，每跳 14.0 ms，总时延 42.0 ms。",
            "5 Mbps：传输 2.4 ms，每跳 4.4 ms，总时延 13.2 ms。",
            "10 Mbps：传输 1.2 ms，每跳 3.2 ms，总时延 9.6 ms。",
            "20 Mbps：传输 0.6 ms，每跳 2.6 ms，总时延 7.8 ms。",
            "100 Mbps：传输 0.12 ms，每跳 2.12 ms，总时延 6.36 ms。",
            "练习：把三段链路共用速率调到 4 Mbps，使总时延恰好等于 15.0 ms。",
            "思考：为什么速率再高，三跳总时延也不能低于 6 ms？",
        ],
    ),
    (
        "第三章 可靠传输：丢了怎么办",
        [
            "原创教学源稿，不是任何教材的副本。",
            "学习目标：",
            "1. 描述停等协议中 DATA 与 ACK 的基本往返。",
            "2. 用超时判断数据或确认没有按时返回。",
            "3. 解释重传怎样修复丢失。",
            "4. 用序列号识别重复数据，保证应用只收到一次新数据。",
            "假设：单向传播 20 ms，往返 40 ms，超时 60 ms；忽略发送时间和拥塞。",
        ],
    ),
    (
        "3.1 正常往返",
        [
            "发送方在 0 ms 发送 DATA，序列号为 0。",
            "接收方在 20 ms 收到 DATA，并发送 ACK 0。",
            "发送方在 40 ms 收到 ACK 0，本次传输完成。",
            "正常场景：数据发送 1 次。",
            "接收方重复见到 0 次。",
            "应用新交付 1 次。",
            "完成时间 40 ms。",
        ],
    ),
    (
        "3.2 超时与两种丢失",
        [
            "如果 DATA 丢失，接收方不会发送 ACK。",
            "发送方等到 60 ms 超时，再发送一次 DATA。",
            "重传数据在 80 ms 到达，ACK 在 100 ms 返回。",
            "如果 DATA 到达但 ACK 丢失，发送方仍会超时并重传。",
            "接收方再次见到序列号 0，丢弃重复副本并重发 ACK 0。",
            "确认丢失时，应用新交付仍为 1 次。",
            "两种丢失都在 100 ms 完成，但重复次数不同。",
        ],
    ),
    (
        "3.3 可靠不等于没有重复",
        [
            "网络可能重复投递同一个数据包。",
            "可靠传输的目标是让应用得到一次新数据，而不是让网络从不出现重复。",
            "正常：1 次发送，0 次重复，1 次应用交付，40 ms 完成。",
            "数据丢失：2 次发送，0 次重复，1 次应用交付，100 ms 完成。",
            "确认丢失：2 次发送，1 次重复，1 次应用交付，100 ms 完成。",
            "练习：选择“丢确认”故障，检查发送、重复和交付次数。",
            "思考：为什么 ACK 丢失时要重传，而重复 DATA 不能再交给应用？",
        ],
    ),
]


def main():
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    toc = []
    for number, title in CHAPTERS:
        toc.append([1, title, 1 + (number - 1) * 4])
    for index, (title, lines) in enumerate(PAGES, 1):
        page = doc.new_page(width=595, height=842)
        heading = pymupdf.Rect(54, 54, 541, 116)
        result = page.insert_textbox(
            heading,
            title,
            fontsize=19 if (index - 1) % 4 == 0 else 17,
            fontname="china-ss",
            color=(0.12, 0.16, 0.20),
            align=pymupdf.TEXT_ALIGN_LEFT,
            lineheight=1.25,
        )
        if result < 0:
            raise RuntimeError(f"heading does not fit on page {index}: {result}")
        body = pymupdf.Rect(54, 136, 541, 760)
        result = page.insert_textbox(
            body,
            "\n\n".join(lines),
            fontsize=12,
            fontname="china-s",
            color=(0.18, 0.20, 0.22),
            align=pymupdf.TEXT_ALIGN_LEFT,
            lineheight=1.65,
        )
        if result < 0:
            raise RuntimeError(f"body does not fit on page {index}: {result}")
        if (index - 1) % 4 != 0:
            toc.append([2, title, index])
        footer = "Papermorph 三章私有 PoC · 原创源稿 · 仅用于工具链与教学交互验证"
        page.insert_text(
            (54, 806),
            footer,
            fontsize=8,
            fontname="china-s",
            color=(0.45, 0.46, 0.47),
        )
    doc.set_toc(toc)
    doc.save(TARGET, garbage=4, deflate=True)
    doc.close()
    with pymupdf.open(TARGET) as check:
        if len(check) != len(PAGES):
            raise RuntimeError("generated PDF page count mismatch")
        extracted = "\n".join(page.get_text() for page in check)
        for phrase in ("12000", "11.2", "36/R", "15.0", "ACK", "100 ms"):
            if phrase not in extracted:
                raise RuntimeError(f"generated PDF is missing {phrase!r}")
        if len(check.get_toc()) != 12:
            raise RuntimeError("generated PDF outline mismatch")
    print(f"wrote {TARGET} ({len(PAGES)} pages, {len(CHAPTERS)} chapters)")


if __name__ == "__main__":
    main()

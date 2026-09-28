// 画像の中の文字を、Mac の文字認識（Vision）で読み取る。インストール不要（macOS 13 以降、日本語対応）。
// 使い方: swiftc -O screen_ocr.swift -o screen_ocr && ./screen_ocr 画像1.png 画像2.png … > 結果.json
// 出力: {画像のパス: [{"text": 文字, "x": 左, "y": 上, "w": 幅, "h": 高さ, "conf": 確からしさ}]}（位置は画像に対する 0〜1 の比）
import Foundation
import Vision
import AppKit

var result: [String: [[String: Any]]] = [:]
for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        result[path] = []
        continue
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["ja-JP", "en-US"]
    req.usesLanguageCorrection = true
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    try? handler.perform([req])
    var items: [[String: Any]] = []
    for obs in req.results ?? [] {
        guard let top = obs.topCandidates(1).first else { continue }
        let b = obs.boundingBox   // 左下が原点
        items.append(["text": top.string, "x": b.minX, "y": 1 - b.maxY, "w": b.width, "h": b.height, "conf": top.confidence])
    }
    result[path] = items
}
let data = try! JSONSerialization.data(withJSONObject: result, options: [])
FileHandle.standardOutput.write(data)

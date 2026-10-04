// 画像の中の顔を Mac の顔検出（Vision）で探す小さな道具。make_zukai.py が図解のワイプの切り出しに使う（初回に swiftc でコンパイルし、
// 図解のフォルダの out/_bin/facedet に置く）。元：環境設定 v004 の hl/_work/face.swift。
// 使い方: facedet 画像.png …  → 1行に「ファイル名 中心x,中心y,幅,高さ …」（画素。顔の数だけ。左上が 0,0）
import Vision
import AppKit
for p in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: p), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print(p, "ERR"); continue }
    let req = VNDetectFaceRectanglesRequest()
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    let W = Double(cg.width), H = Double(cg.height)
    var out: [String] = []
    for f in (req.results ?? []) {
        let b = f.boundingBox
        out.append(String(format: "%.0f,%.0f,%.0f,%.0f", b.midX*W, (1-b.midY)*H, b.width*W, b.height*H))
    }
    print((p as NSString).lastPathComponent, out.joined(separator: " "))
}

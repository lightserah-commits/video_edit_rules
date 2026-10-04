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

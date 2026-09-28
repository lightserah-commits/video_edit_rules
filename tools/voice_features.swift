// 字幕ごとの声の特徴（声の高さ F0 と、メル帯域の対数パワーの平均＝声色）を測る。話者の判別（tools/speaker_id.py）に使う。
// Mac の標準（Accelerate）だけで動く。インストール不要。2026-09-26 画面解説の案件で作った（話者の分かっている字幕で正解率 92〜96%）。
// 使い方: swiftc -O tools/voice_features.swift -o <作業フォルダ>/voice_features && <作業フォルダ>/voice_features <作業フォルダ>
//   <作業フォルダ>/camera_16k.f32（16kHz モノラル float32、ffmpeg -ac 1 -ar 16000 -f f32le）と cap_ranges.json（[{idx, spk, ranges:[[秒,秒]…]}]）を読み、
//   voicefeat.json（[{idx, spk, n, f0_med, f0_n, mel:[24]}]）を書く
import Foundation
import Accelerate

let dir = CommandLine.arguments[1]
let sr = 16000
let raw = try! Data(contentsOf: URL(fileURLWithPath: dir + "/camera_16k.f32"))
let samples: [Float] = raw.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
let capsData = try! Data(contentsOf: URL(fileURLWithPath: dir + "/cap_ranges.json"))
let caps = try! JSONSerialization.jsonObject(with: capsData) as! [[String: Any]]

let N = 512, hop = 160, nMel = 24
let log2n = vDSP_Length(9)
let fft = vDSP.FFT(log2n: log2n, radix: .radix2, ofType: DSPSplitComplex.self)!
var window = [Float](repeating: 0, count: N)
vDSP_hann_window(&window, vDSP_Length(N), Int32(vDSP_HANN_NORM))
// メルフィルタ（60Hz〜7600Hz）
func hz2mel(_ f: Float) -> Float { 2595 * log10(1 + f / 700) }
func mel2hz(_ m: Float) -> Float { 700 * (pow(10, m / 2595) - 1) }
let mlo = hz2mel(60), mhi = hz2mel(7600)
var edges: [Float] = (0...(nMel + 1)).map { mel2hz(mlo + (mhi - mlo) * Float($0) / Float(nMel + 1)) }
let bins = edges.map { Int(($0 / Float(sr)) * Float(N)) }

var results: [[String: Any]] = []
for c in caps {
    let ranges = c["ranges"] as! [[Double]]
    var frames: [(e: Float, f0: Float, mel: [Float])] = []
    for r in ranges {
        let i0 = max(0, Int(r[0] * Double(sr))), i1 = min(samples.count, Int(r[1] * Double(sr)))
        var p = i0
        while p + N <= i1 {
            let seg = Array(samples[p..<(p + N)])
            var e: Float = 0
            vDSP_svesq(seg, 1, &e, vDSP_Length(N))
            // 声の高さ：自己相関（70〜350Hz）
            var best: Float = 0, bestLag = 0
            var r0: Float = 0
            vDSP_dotpr(seg, 1, seg, 1, &r0, vDSP_Length(N))
            for lag in (sr / 350)...(sr / 70) {
                var v: Float = 0
                vDSP_dotpr(seg, 1, Array(seg[lag...]), 1, &v, vDSP_Length(N - lag))
                if v > best { best = v; bestLag = lag }
            }
            let voiced = r0 > 0 && best / r0 > 0.45
            // メル帯域のパワー
            var w = [Float](repeating: 0, count: N)
            vDSP_vmul(seg, 1, window, 1, &w, 1, vDSP_Length(N))
            var re = [Float](repeating: 0, count: N / 2), im = [Float](repeating: 0, count: N / 2)
            var mags = [Float](repeating: 0, count: N / 2)
            re.withUnsafeMutableBufferPointer { rp in
                im.withUnsafeMutableBufferPointer { ip in
                    var sc = DSPSplitComplex(realp: rp.baseAddress!, imagp: ip.baseAddress!)
                    w.withUnsafeBufferPointer { wp in
                        wp.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: N / 2) { cp in
                            vDSP_ctoz(cp, 2, &sc, 1, vDSP_Length(N / 2))
                        }
                    }
                    fft.forward(input: sc, output: &sc)
                    vDSP_zvmags(&sc, 1, &mags, 1, vDSP_Length(N / 2))
                }
            }
            var mel = [Float](repeating: 0, count: nMel)
            for m in 0..<nMel {
                var s: Float = 0
                let a = bins[m], b = bins[m + 1], cc = bins[m + 2]
                if b > a { for k in a..<b { s += mags[k] * Float(k - a) / Float(b - a) } }
                if cc > b { for k in b..<cc { s += mags[k] * Float(cc - k) / Float(cc - b) } }
                mel[m] = log10(s + 1e-6)
            }
            frames.append((e, voiced ? Float(sr) / Float(bestLag) : 0, mel))
            p += hop
        }
    }
    var out: [String: Any] = ["idx": c["idx"]!, "spk": c["spk"]!, "n": frames.count]
    if frames.count >= 5 {
        let sorted = frames.sorted { $0.e > $1.e }
        let top = Array(sorted.prefix(max(5, Int(Double(sorted.count) * 0.5))))
        let f0s = top.map { $0.f0 }.filter { $0 > 0 }.sorted()
        out["f0_med"] = f0s.isEmpty ? 0 : f0s[f0s.count / 2]
        out["f0_n"] = f0s.count
        var meanMel = [Float](repeating: 0, count: nMel)
        for f in top { for m in 0..<nMel { meanMel[m] += f.mel[m] / Float(top.count) } }
        out["mel"] = meanMel
    }
    results.append(out)
}
let json = try! JSONSerialization.data(withJSONObject: results)
try! json.write(to: URL(fileURLWithPath: dir + "/voicefeat.json"))
print("done", results.count)

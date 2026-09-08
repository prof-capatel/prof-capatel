import 'dart:async';
import 'dart:html' as html;
import 'dart:typed_data';
import 'dart:ui_web' as ui_web;
import 'package:flutter/widgets.dart';

class CameraWebService {
  html.VideoElement? _videoElement;
  html.MediaStream? _mediaStream;
  String _viewType = 'flutter-web-camera-view';
  bool _isInitialized = false;

  bool get isInitialized => _isInitialized;
  String get viewType => _viewType;
  html.VideoElement? get videoElement => _videoElement;

  /// Initializes the HTML5 video element and requests Chrome camera permissions
  Future<void> initialize({bool useFrontCamera = true}) async {
    _viewType = 'flutter-web-camera-view-${DateTime.now().millisecondsSinceEpoch}';

    _videoElement = html.VideoElement()
      ..autoplay = true
      ..muted = true
      ..style.width = '100%'
      ..style.height = '100%'
      ..style.objectFit = 'cover'
      ..style.transform = useFrontCamera ? 'scaleX(-1)' : 'scaleX(1)';

    // Register platform view for Flutter Web rendering
    ui_web.platformViewRegistry.registerViewFactory(
      _viewType,
      (int viewId) => _videoElement!,
    );

    final constraints = {
      'audio': false,
      'video': {
        'facingMode': useFrontCamera ? 'user' : 'environment',
        'width': {'ideal': 1280},
        'height': {'ideal': 960},
      }
    };

    try {
      _mediaStream = await html.window.navigator.mediaDevices?.getUserMedia(constraints);
      if (_mediaStream != null && _videoElement != null) {
        _videoElement!.srcObject = _mediaStream;
        _isInitialized = true;
      } else {
        throw Exception('Camera media stream is null');
      }
    } catch (e) {
      _isInitialized = false;
      throw Exception('Failed to access camera in Chrome: $e. Please allow camera permissions.');
    }
  }

  /// Captures the current camera video frame as JPEG byte array (Uint8List)
  Future<Uint8List?> captureFrame() async {
    if (_videoElement == null || !_isInitialized) return null;

    final width = _videoElement!.videoWidth > 0 ? _videoElement!.videoWidth : 640;
    final height = _videoElement!.videoHeight > 0 ? _videoElement!.videoHeight : 480;

    final canvas = html.CanvasElement(width: width, height: height);
    final ctx = canvas.context2D;

    // Draw frame without mirroring for accurate 1:N facial biometric extraction
    ctx.drawImage(_videoElement!, 0, 0);

    final completer = Completer<Uint8List?>();
    canvas.toBlob('image/jpeg', 0.92).then((blob) {
      final reader = html.FileReader();
      reader.readAsArrayBuffer(blob);
      reader.onLoadEnd.listen((_) {
        if (reader.result != null) {
          completer.complete(Uint8List.fromList(reader.result as List<int>));
        } else {
          completer.complete(null);
        }
      });
    }).catchError((err) {
      completer.completeError('Canvas capture failed: $err');
    });

    return completer.future;
  }

  /// Disposes active media tracks to free Chrome camera hardware
  void dispose() {
    try {
      _mediaStream?.getTracks().forEach((track) => track.stop());
      _videoElement?.srcObject = null;
      _videoElement?.remove();
      _isInitialized = false;
    } catch (_) {}
  }
}

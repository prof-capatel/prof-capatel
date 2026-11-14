import 'dart:async';
import 'dart:typed_data';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

class CameraWebService {
  CameraController? _controller;
  bool _isInitialized = false;
  String _viewType = 'flutter-mobile-camera-view';

  bool get isInitialized => _isInitialized && _controller != null && _controller!.value.isInitialized;
  CameraController? get controller => _controller;
  String get viewType => _viewType;
  dynamic get videoElement => null;

  /// Initializes mobile camera service strictly with front-facing camera
  Future<void> initialize({bool useFrontCamera = true}) async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        throw Exception('No camera sensors available on device.');
      }

      final targetDirection = useFrontCamera ? CameraLensDirection.front : CameraLensDirection.back;
      final selectedCamera = cameras.firstWhere(
        (c) => c.lensDirection == targetDirection,
        orElse: () => cameras.first,
      );

      _controller = CameraController(
        selectedCamera,
        ResolutionPreset.medium,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );

      await _controller!.initialize();
      _isInitialized = true;
      _viewType = 'flutter-mobile-camera-view-${DateTime.now().millisecondsSinceEpoch}';
    } catch (e) {
      _isInitialized = false;
      debugPrint('Mobile CameraController initialization error: $e');
      rethrow;
    }
  }

  /// Builds the embedded live camera feed widget
  Widget buildPreview() {
    if (_controller != null && _controller!.value.isInitialized) {
      return CameraPreview(_controller!);
    }
    return const Center(
      child: CircularProgressIndicator(color: Color(0xFF6366F1)),
    );
  }

  /// Captures a camera photo using in-app camera controller
  Future<Uint8List?> captureFrame() async {
    if (_controller == null || !_controller!.value.isInitialized) {
      return null;
    }
    try {
      final XFile photo = await _controller!.takePicture();
      return await photo.readAsBytes();
    } catch (e) {
      debugPrint('Mobile in-app camera capture error: $e');
      return null;
    }
  }

  /// Disposes active camera
  void dispose() {
    _isInitialized = false;
    _controller?.dispose();
    _controller = null;
  }
}

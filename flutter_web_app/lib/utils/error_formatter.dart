class ErrorFormatter {
  /// Transforms raw technical exceptions and stack traces into clean, polite, and actionable user messages.
  static String format(dynamic error) {
    if (error == null) return 'An unexpected issue occurred. Please try again.';

    final raw = error.toString().trim();

    if (raw.isEmpty) return 'An unexpected error occurred. Please try again.';

    // 1. Network / DNS / Host Unreachable
    if (raw.contains('SocketException') ||
        raw.contains('Failed host lookup') ||
        raw.contains('No address associated with hostname') ||
        raw.contains('Network is unreachable')) {
      return 'Unable to reach the server. Please check your internet connection or server URL.';
    }

    // 2. Connection refused / Offline server
    if (raw.contains('Connection refused') || raw.contains('ECONNREFUSED')) {
      return 'Could not connect to the attendance server. Please ensure the server is active.';
    }

    // 3. Timeouts
    if (raw.contains('TimeoutException') || raw.contains('timed out') || raw.contains('ETIMEDOUT')) {
      return 'Connection timed out. The server took too long to respond. Please try again.';
    }

    // 4. SSL / TLS Handshake
    if (raw.contains('HandshakeException') || raw.contains('CERTIFICATE_VERIFY_FAILED')) {
      return 'Secure connection error (SSL). Please verify the server certificate or URL.';
    }

    // 5. HTTP Client general errors
    if (raw.contains('ClientException with SocketException')) {
      return 'Network connection failure. Please verify your Wi-Fi or mobile data.';
    }

    // 6. JSON Parsing / Malformed responses
    if (raw.contains('FormatException') || raw.contains('Unexpected character')) {
      return 'Unexpected response from the server. Please check your connection or contact support.';
    }

    // 7. HTTP Status Code patterns
    if (raw.contains('401') || raw.toLowerCase().contains('unauthorized')) {
      if (raw.toLowerCase().contains('invalid username or password') ||
          raw.toLowerCase().contains('invalid credentials')) {
        return 'Invalid username or password. Please verify your credentials and try again.';
      }
      return 'Authentication failed. Please verify your credentials or organization code.';
    }

    if (raw.contains('403') || raw.toLowerCase().contains('forbidden')) {
      return 'Access denied. Please check with your organization administrator.';
    }

    if (raw.contains('404') || raw.toLowerCase().contains('not found')) {
      return 'The requested organization or service could not be found.';
    }

    if (raw.contains('500') ||
        raw.contains('502') ||
        raw.contains('503') ||
        raw.toLowerCase().contains('internal server error')) {
      return 'The attendance server encountered a temporary error. Please try again in a moment.';
    }

    // Clean up technical prefixes like "Exception: ", "ClientException: "
    String cleaned = raw
        .replaceAll(RegExp(r'^(Exception|ClientException|HttpException|StateError):\s*', caseSensitive: false), '')
        .trim();

    return cleaned.isNotEmpty ? cleaned : 'Unable to complete request. Please try again.';
  }
}

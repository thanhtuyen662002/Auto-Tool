import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  copied: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null, copied: false };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo });
    console.error('[ErrorBoundary] Caught error:', error, errorInfo);
  }

  handleGoHome = (): void => {
    // Reset state and navigate to home via hard reload so route state is cleared
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.href = '/';
  };

  handleCopyError = (): void => {
    const { error, errorInfo } = this.state;
    const text = [
      `Error: ${error?.message ?? 'Unknown error'}`,
      error?.stack ?? '',
      errorInfo?.componentStack ?? '',
    ].join('\n\n');
    navigator.clipboard.writeText(text).then(() => {
      this.setState({ copied: true });
      setTimeout(() => this.setState({ copied: false }), 2000);
    });
  };

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children;
    }

    const { error, copied } = this.state;

    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-surface px-6 py-12">
        <div className="w-full max-w-lg rounded-xl border border-red-200 bg-white p-8 shadow-panel">
          {/* Icon */}
          <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-red-50">
            <svg
              className="h-7 w-7 text-red-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
              />
            </svg>
          </div>

          <h1 className="mb-2 text-xl font-semibold text-ink">Đã xảy ra lỗi không mong muốn</h1>
          <p className="mb-5 text-sm text-muted">
            Giao diện gặp sự cố và cần được tải lại. Dữ liệu render của bạn không bị ảnh hưởng.
          </p>

          {error?.message && (
            <div className="mb-5 rounded-md bg-red-50 px-4 py-3 font-mono text-xs text-red-700 break-all">
              {error.message}
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            <button
              id="error-boundary-go-home"
              className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
              type="button"
              onClick={this.handleGoHome}
            >
              Quay về trang chủ
            </button>
            <button
              id="error-boundary-copy-error"
              className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand transition-colors"
              type="button"
              onClick={this.handleCopyError}
            >
              {copied ? '✅ Đã sao chép' : 'Sao chép lỗi'}
            </button>
            <button
              id="error-boundary-reload"
              className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-muted hover:text-ink transition-colors"
              type="button"
              onClick={() => window.location.reload()}
            >
              Tải lại trang
            </button>
          </div>
        </div>
      </div>
    );
  }
}

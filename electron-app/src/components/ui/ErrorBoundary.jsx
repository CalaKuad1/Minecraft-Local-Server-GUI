import React from 'react';

export default class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error('[ErrorBoundary]', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex items-center justify-center h-full p-8">
                    <div className="text-center">
                        <div className="text-red-400 text-sm font-minecraft uppercase tracking-widest mb-4">
                            Something went wrong
                        </div>
                        <p className="text-zinc-500 text-xs mb-4 max-w-md break-words">
                            {this.state.error?.message || 'Unknown error'}
                        </p>
                        <button
                            onClick={() => this.setState({ hasError: false, error: null })}
                            className="px-4 py-2 bg-white/5 border border-white/10 rounded-sm text-xs text-white hover:bg-white/10 transition-colors"
                        >
                            Retry
                        </button>
                    </div>
                </div>
            );
        }
        return this.props.children;
    }
}

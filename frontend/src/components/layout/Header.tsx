import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export const Header: React.FC = () => {
  const location = useLocation();

  return (
    <header className="sticky top-0 z-30 w-full border-b border-hairline bg-canvas/90 backdrop-blur-xs">
      <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4 sm:px-6">
        <Link
          to="/"
          className="font-serif text-2xl font-medium tracking-tight text-ink transition-colors hover:text-primary"
        >
          VietNorm
        </Link>
        <nav className="flex items-center gap-6">
          <Link
            to="/about"
            className={`text-sm font-medium transition-colors ${
              location.pathname === '/about'
                ? 'text-primary'
                : 'text-muted hover:text-ink'
            }`}
          >
            Giới thiệu
          </Link>
        </nav>
      </div>
    </header>
  );
};

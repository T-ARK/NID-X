import React from 'react';
import { Outlet } from 'react-router-dom';
import { TopStatusBar } from '../components/TopStatusBar';
import { NavigationRail, MobileNavigation } from '../components/NavigationRail';
import './MainLayout.css';

export function MainLayout() {
  return (
    <>
      <TopStatusBar />
      <NavigationRail />
      <MobileNavigation />
      <main className="main-content" id="main">
        <Outlet />
      </main>
    </>
  );
}

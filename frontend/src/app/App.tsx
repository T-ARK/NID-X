import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import Overview from '../pages/Overview';
import TrafficAnalysis from '../pages/TrafficAnalysis';
import ModelPerformance from '../pages/ModelPerformance';
import Alerts from '../pages/Alerts';
import Reports from '../pages/Reports';
import Settings from '../pages/Settings';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Overview />} />
        <Route path="traffic" element={<TrafficAnalysis />} />
        <Route path="performance" element={<ModelPerformance />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="reports" element={<Reports />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

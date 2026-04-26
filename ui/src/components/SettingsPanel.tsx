import { type ChangeEvent } from 'react';
import { Sliders } from 'lucide-react';
import './SettingsPanel.css';

interface Config {
  width: number;
  height: number;
  padding: number;
  bg_color: string;
  face_confidence: number;
  weight_strategy: string;
  face_padding: number;
  face_only: boolean;
  hero: boolean;
  hero_scale: number;
}

interface SettingsPanelProps {
  config: Config;
  onChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
}

export default function SettingsPanel({ config, onChange }: SettingsPanelProps) {
  return (
    <aside className="settings" id="settings-panel">
      <div className="settings__header">
        <Sliders size={18} strokeWidth={1.5} />
        <h2>Settings</h2>
      </div>

      {/* ---- Canvas ---- */}
      <details className="settings__section" open>
        <summary className="settings__section-title">Canvas</summary>
        <div className="settings__section-body">
          <label className="field" id="field-width">
            <span className="field__label">Width</span>
            <div className="field__input-group">
              <input
                type="number"
                name="width"
                className="field__input"
                value={config.width}
                onChange={onChange}
                min={500}
                step={100}
              />
              <span className="field__unit">px</span>
            </div>
          </label>

          <label className="field" id="field-height">
            <span className="field__label">Height</span>
            <div className="field__input-group">
              <input
                type="number"
                name="height"
                className="field__input"
                value={config.height}
                onChange={onChange}
                min={500}
                step={100}
              />
              <span className="field__unit">px</span>
            </div>
          </label>

          <label className="field" id="field-padding">
            <span className="field__label">Gap</span>
            <div className="field__input-group">
              <input
                type="number"
                name="padding"
                className="field__input"
                value={config.padding}
                onChange={onChange}
                min={0}
                max={50}
              />
              <span className="field__unit">px</span>
            </div>
          </label>

          <label className="field" id="field-bg-color">
            <span className="field__label">Background</span>
            <div className="field__color-row">
              <input
                type="color"
                name="bg_color"
                className="field__color-swatch"
                value={config.bg_color}
                onChange={onChange}
              />
              <span className="field__color-hex">{config.bg_color}</span>
            </div>
          </label>
        </div>
      </details>

      {/* ---- Layout ---- */}
      <details className="settings__section" open>
        <summary className="settings__section-title">Layout</summary>
        <div className="settings__section-body">
          <label className="field" id="field-weight-strategy">
            <span className="field__label">Weight strategy</span>
            <select
              name="weight_strategy"
              className="field__select"
              value={config.weight_strategy}
              onChange={onChange}
            >
              <option value="equal">Equal</option>
              <option value="faces">Faces (prioritize groups)</option>
              <option value="resolution">Resolution (prioritize HD)</option>
            </select>
          </label>

          <div className="field" id="field-hero">
            <div className="field__toggle-row">
              <span className="field__label">Hero layout</span>
              <label className="toggle">
                <input
                  type="checkbox"
                  name="hero"
                  checked={config.hero}
                  onChange={onChange}
                />
                <span className="toggle__track"></span>
              </label>
            </div>
          </div>

          {config.hero && (
            <label className="field" id="field-hero-scale">
              <div className="field__label-row">
                <span className="field__label">Hero scale</span>
                <span className="field__value">{config.hero_scale}</span>
              </div>
              <input
                type="range"
                name="hero_scale"
                className="field__range"
                value={config.hero_scale}
                onChange={onChange}
                min={0.3}
                max={0.7}
                step={0.05}
              />
              <p className="field__hint">
                Click the ⭐ on any thumbnail to mark it as hero.
              </p>
            </label>
          )}
        </div>
      </details>

      {/* ---- Detection ---- */}
      <details className="settings__section">
        <summary className="settings__section-title">Detection</summary>
        <div className="settings__section-body">
          <label className="field" id="field-face-confidence">
            <div className="field__label-row">
              <span className="field__label">Face confidence</span>
              <span className="field__value">{config.face_confidence}</span>
            </div>
            <input
              type="range"
              name="face_confidence"
              className="field__range"
              value={config.face_confidence}
              onChange={onChange}
              min={0.1}
              max={0.9}
              step={0.05}
            />
          </label>

          <label className="field" id="field-face-padding">
            <div className="field__label-row">
              <span className="field__label">Face padding</span>
              <span className="field__value">{config.face_padding}</span>
            </div>
            <input
              type="range"
              name="face_padding"
              className="field__range"
              value={config.face_padding}
              onChange={onChange}
              min={0.1}
              max={0.8}
              step={0.05}
            />
          </label>

          <div className="field" id="field-face-only">
            <div className="field__toggle-row">
              <span className="field__label">Face-only protection</span>
              <label className="toggle">
                <input
                  type="checkbox"
                  name="face_only"
                  checked={config.face_only}
                  onChange={onChange}
                />
                <span className="toggle__track"></span>
              </label>
            </div>
            <p className="field__hint">Only protect face area (skip body estimation).</p>
          </div>
        </div>
      </details>
    </aside>
  );
}

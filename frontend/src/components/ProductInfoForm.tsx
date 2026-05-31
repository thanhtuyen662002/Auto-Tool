import type { ProjectConfig } from '../types/project';
import NumberInput from './NumberInput';
import TextArea from './TextArea';
import TextInput from './TextInput';

interface ProductInfoFormProps {
  config: ProjectConfig;
  onChange: (config: ProjectConfig) => void;
}

export default function ProductInfoForm({ config, onChange }: ProductInfoFormProps) {
  const update = (patch: Partial<ProjectConfig>) => onChange({ ...config, ...patch });
  const updateProduct = (patch: Partial<ProjectConfig['product']>) =>
    onChange({ ...config, product: { ...config.product, ...patch } });
  const updateRender = (patch: Partial<ProjectConfig['render']>) =>
    onChange({ ...config, render: { ...config.render, ...patch } });

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput
          label="Tên dự án"
          value={config.project_name}
          required
          onChange={(project_name) => update({ project_name })}
        />
        <TextInput
          label="Thương hiệu"
          value={config.product.brand}
          onChange={(brand) => updateProduct({ brand })}
        />
      </div>

      <TextInput
        label="Đường dẫn thư mục video nguồn"
        value={config.source_folder}
        onChange={(source_folder) => update({ source_folder })}
      />
      <TextInput
        label="Đường dẫn thư mục đầu ra"
        value={config.output_folder}
        onChange={(output_folder) => update({ output_folder })}
      />

      <TextInput
        label="Tên sản phẩm"
        value={config.product.name}
        onChange={(name) => updateProduct({ name })}
      />
      <TextArea
        label="Mô tả"
        value={config.product.description}
        rows={3}
        onChange={(description) => updateProduct({ description })}
      />
      <TextArea
        label="Tính năng nổi bật"
        value={config.product.features.join('\n')}
        rows={5}
        onChange={(value) =>
          updateProduct({
            features: value
              .split('\n')
          })
        }
      />
      <TextInput label="CTA" value={config.product.cta} onChange={(cta) => updateProduct({ cta })} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <NumberInput
          label="Số lượng video"
          value={config.render.output_count}
          min={1}
          onChange={(output_count) => updateRender({ output_count })}
        />
        <NumberInput
          label="Thời lượng"
          value={config.render.duration}
          min={3}
          onChange={(duration) => updateRender({ duration })}
        />
        <TextInput
          label="Độ phân giải"
          value={config.render.resolution}
          onChange={(resolution) => updateRender({ resolution })}
        />
        <NumberInput
          label="FPS"
          value={config.render.fps}
          min={1}
          onChange={(fps) => updateRender({ fps })}
        />
      </div>
    </div>
  );
}

## Parameters
input (required) - input wind speed raster  
output (required) - output damage shapefile  
output raster --out_raster (optional) - save the output damage raster

```json
{
  "command": [
    {
      "type": "input",
      "value": "s3://bucket/path/to/max_wind.tif"
    },
    {
      "type": "output",
      "value": "s3://bucket/path/to/shp/output.shp"
    },
    {
      "type": "output",
      "name": "--out_raster",
      "value": "s3://bucket/path/to/shp/output.tif"
    }
  ],
  "output": ["s3://bucket/path/to/shp"]
}
```

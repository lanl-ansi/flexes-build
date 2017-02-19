## Parameters
aoi (required) - the area used to perform the calculation  
fields -f --fields (optional) - the fields to calculate as a semi-colon delimited string, 
default Total  Population  
bin -b --bin (optional) - field in the aoi used to bin results  
disaggregate -d --disag (optional) - bin results by predefined boundaries (state, county
or fema)  
output -o --output (required) - location to save the output JSON file

```json
{
  "command": [
    {
      "type": "input",
      "value": "s3://bucket/path/to/shp/my_area.shp"
    },
    {
      "type": "parameter",
      "name": "--fields",
      "value": "'Total Population;Total Jobs'"
    },
    {
      "type": "output",
      "name": "--output",
      "value": "s3://bucket/path/to/output.json"
    }
  ],
  "input": ["s3://bucket/path/to/shp"]
}
```

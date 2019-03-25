package konaktauth

import (
	"encoding/json"
	"github.com/influxdata/telegraf"
	"github.com/influxdata/telegraf/plugins/processors"
	"github.com/pkg/errors"
	"log"
	"net/http"
	"time"
)

type KontaktAuth struct {
	ApiAddress            string            `toml:"api_address"`

	Client *http.Client
}

type apiCompany struct {
	ID                string
	SubscriptionPlans []string
}

type apiManager struct {
	ID      string
	Company apiCompany
}

var SampleConfig = `
api_address="https://testapi.kontakt.io"
`

const acceptHeader = "application/vnd.com.kontakt+json;version=10"
var unknownApiKeyDuration = time.Minute * 10
const apiKeyTag = "Api-Key"

var cache = make(map[string]apiManager)
var unknownCache = make(map[string]time.Time)

func (ka *KontaktAuth) getManager(apiKey string) (apiManager, error) {
	if manager, ok := cache[apiKey]; ok {
		return manager, nil
	}
	if t, ok := unknownCache[apiKey]; ok {
		if t.Add(unknownApiKeyDuration).Before(t) {
			delete(unknownCache, apiKey)
		} else {
			return apiManager{}, errors.New("unauthorized")
		}
	}
	var manager apiManager
	err := ka.get("manager/me", apiKey, &manager)
	if err == nil {
		cache[apiKey] = manager
	} else {
		log.Printf("Error %v", err)
		unknownCache[apiKey] = time.Now()
	}
	return manager, err
}

func (ka *KontaktAuth) get(path, apiKey string, result interface{}) error {
	request, err := http.NewRequest("GET", ka.ApiAddress+path, nil)
	if err != nil {
		return err
	}
	request.Header.Add("Accept", acceptHeader)
	request.Header.Add("Api-Key", apiKey)
	response, err := ka.Client.Do(request)
	if err != nil {
		return err
	}
	if err := json.NewDecoder(response.Body).Decode(result); err != nil {
		return err
	}
	return nil
}

func (p *KontaktAuth) SampleConfig() string {
	return SampleConfig
}

func (p *KontaktAuth) Description() string {
	return "Authenticates telemetry and fills companyId"
}

func (p *KontaktAuth) Apply(metrics ...telegraf.Metric) []telegraf.Metric {
	for _, metric := range metrics {
		if !metric.HasTag(apiKeyTag) {
			continue
		}
		apiKey, _ := metric.GetTag(apiKeyTag)
		manager, err := p.getManager(apiKey)
		if err != nil {
			continue
		}
		metric.RemoveTag(apiKeyTag)
		metric.AddTag("companyId", manager.Company.ID)
	}
	return metrics
}

func New() *KontaktAuth {
	kontaktAuth := KontaktAuth{
		Client: &http.Client{Timeout: time.Second * 5},
	}
	return &kontaktAuth
}

func init() {
	processors.Add("kontaktauth", func() telegraf.Processor {
		return New()
	})
}
